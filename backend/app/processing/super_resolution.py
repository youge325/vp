"""超分辨率算法实现。"""

from typing import Any

import numpy as np

from app.algorithms.base import IAlgorithm
from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner
from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS
from app.utils.onnx_models import create_onnx_session, resolve_onnx_model_path
from app.utils.model_metrics import get_paddlegan_model_detail
from app.algorithms.tensor_backend import ITensorBackend


SUPPORTED_ALGORITHMS: list[dict[str, Any]] = [
    # Phase 8 — ``tensorBackends`` 显式声明该算法支持的 tensor 后端。
    # 当前两个算法都只在 ONNX 路径下有完整实现(见下方 class doc),
    # PyTorch / Paddle 路径返回 NotImplementedError。
    {
        "name": "placeholder",
        "family": "onnx_super_resolution",
        "tensorBackends": ["onnx"],
        "models": [],
        "inputFrameMode": "none",
    },
    {
        "name": "realesrgan-plan",
        "family": "onnx_super_resolution",
        "tensorBackends": ["onnx"],
        "models": [],
        "inputFrameMode": "none",
    },
    *[
        {
            "name": spec.model_id,
            "family": "paddlegan_vsr",
            "tensorBackends": ["paddle"],
            "models": ["x4"],
            "scaleFactors": [4],
            "fixedScaleFactor": 4,
            "defaultNumFrames": spec.default_num_frames,
            "sequenceMode": spec.sequence_mode,
            "inputFrameMode": "fixed_window" if spec.sequence_mode == "window" else "editable_chunk",
            "modelDetails": [get_paddlegan_model_detail(spec.model_id)],
        }
        for spec in PADDLEGAN_VSR_SPECS.values()
    ],
]


class SuperResolutionAlgorithm(IAlgorithm):
    """
    超分辨率算法。当前仅 ONNX 后端有完整实现。

    - ONNX backend:运行 NCHW RGB float32 image-to-image 推理,按 scale_factor 验证输出尺寸。
    - 其它 backend(pytorch / paddle / numpy):**未实现**。``validate()`` 返回 False,
      ``process_frame`` 抛 ``NotImplementedError``;planning 层会通过
      ``_verify_super_resolution_backend`` 提前拦截无效组合。

    未来计划:Real-ESRGAN 等其它算法、多倍率(2x/4x)、Tensor 后端实现。
    """

    def __init__(self, tensor_backend: ITensorBackend = None, **kwargs):
        self._tensor_backend = tensor_backend
        self._scale_factor = kwargs.get("scale_factor", 2.0)
        self._algorithm_name = kwargs.get("sr_algorithm", "placeholder")
        self._onnx_model = kwargs.get("onnx_model")
        self._model_dir = kwargs.get("model_dir", "")
        self._engine = kwargs.get("engine", "cuda")
        self._num_frames = int(kwargs.get("num_frames") or kwargs.get("numFrames") or 10)
        self._session = None
        self._input_name = ""
        self._output_name = ""
        self._paddlegan_runner = None

    def process_frame(self, frame: Any, **kwargs) -> Any:
        """处理单帧；ONNX 后端运行 image-to-image 超分，其它后端拒绝执行。"""
        if self._is_paddlegan_vsr():
            raise NotImplementedError("PaddleGAN VSR requires frame-sequence processing.")
        if self._backend_name() != "onnx":
            raise NotImplementedError(
                "Super-resolution is only implemented on the ONNX tensor backend; "
                f"got '{self._backend_name()}'. This should have been caught at planning time."
            )

        session = self._ensure_onnx_session()
        input_tensor = np.asarray(frame, dtype=np.float32)
        if input_tensor.ndim != 4 or input_tensor.shape[0] != 1 or input_tensor.shape[1] != 3:
            raise RuntimeError("ONNX super-resolution input must be NCHW RGB float32 with shape (1, 3, H, W).")

        output = session.run([self._output_name], {self._input_name: input_tensor})[0]
        output_tensor = np.asarray(output, dtype=np.float32)
        self._validate_output_shape(input_tensor, output_tensor)
        return np.clip(output_tensor, 0.0, 1.0).astype(np.float32)

    def _ensure_onnx_session(self):
        if self._session is not None:
            return self._session
        if not self._onnx_model:
            raise FileNotFoundError("ONNX super-resolution model was not selected.")

        from app.utils.dll_paths import register_native_dll_paths

        register_native_dll_paths()
        import onnxruntime as ort

        model_path = resolve_onnx_model_path(
            "super_resolution", self._algorithm_name, self._onnx_model, self._model_dir
        )
        session = create_onnx_session(str(model_path), engine=self._engine, ort_module=ort)
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1:
            raise RuntimeError(f"ONNX super-resolution model must expose exactly one input, got {len(inputs)}.")
        if not outputs:
            raise RuntimeError("ONNX super-resolution model does not expose outputs.")

        self._input_name = inputs[0].name
        self._output_name = outputs[0].name
        self._session = session
        return session

    def _validate_output_shape(self, input_tensor: np.ndarray, output_tensor: np.ndarray) -> None:
        if output_tensor.ndim != 4 or output_tensor.shape[0] != 1 or output_tensor.shape[1] != 3:
            raise RuntimeError("ONNX super-resolution output must be NCHW RGB float32 with shape (1, 3, H, W).")

        expected_h = int(round(input_tensor.shape[2] * float(self._scale_factor)))
        expected_w = int(round(input_tensor.shape[3] * float(self._scale_factor)))
        if output_tensor.shape[2] != expected_h or output_tensor.shape[3] != expected_w:
            raise RuntimeError(
                "ONNX super-resolution output size mismatch: "
                f"expected {(expected_h, expected_w)}, got {tuple(output_tensor.shape[2:4])}."
            )

    def _backend_name(self) -> str:
        return self._tensor_backend.get_name() if self._tensor_backend is not None else "numpy"

    def _is_paddlegan_vsr(self) -> bool:
        return self._algorithm_name in PADDLEGAN_VSR_SPECS

    def _ensure_paddlegan_runner(self):
        if self._paddlegan_runner is None:
            self._paddlegan_runner = PaddleGanVsrRunner(
                model_id=self._algorithm_name,
                num_frames=self._num_frames,
                engine=self._engine,
            )
        return self._paddlegan_runner

    def process_frame_batch(self, frames: list[Any], **kwargs) -> list[Any]:
        """逐帧处理批量输入。"""
        return [self.process_frame(frame, **kwargs) for frame in frames]

    def needs_frame_sequence(self) -> bool:
        return self._is_paddlegan_vsr()

    def process_frame_sequence(self, frames: list[Any], **kwargs) -> list[Any]:
        if not self._is_paddlegan_vsr():
            return super().process_frame_sequence(frames, **kwargs)
        return self._ensure_paddlegan_runner().process_frames(
            frames,
            progress_callback=kwargs.get("progress_callback"),
        )

    def get_name(self) -> str:
        if self._is_paddlegan_vsr():
            return f"视频超分辨率算法(PaddleGAN {self._algorithm_name})"
        if self._backend_name() == "onnx":
            return f"超分辨率算法(ONNX {self._onnx_model or '未选择'})"
        return "超分辨率算法(占位)"

    def validate(self) -> bool:
        """验证超分算法配置。

        Phase D.1.1 — 非 ONNX backend 不支持 SR,直接 fail validation。
        正常路径应该在 ``_process_planning._verify_super_resolution_backend``
        提前拦截;此处是第二道防线,防止单独调用算法时静默 no-op。
        """
        if self._is_paddlegan_vsr():
            return self._backend_name() == "paddle" and float(self._scale_factor) == 4.0
        if self._backend_name() != "onnx":
            return False
        return bool(self._onnx_model)

    def get_description(self) -> str:
        if self._is_paddlegan_vsr():
            return f"基于 PaddleGAN 的 4x 视频超分辨率处理({self._algorithm_name})。"
        if self._backend_name() == "onnx":
            return f"基于 ONNX Runtime 的 {self._scale_factor:g}x 视频超分辨率处理。"
        return (
            "视频超分辨率处理占位算法。当前实现：帧→Tensor→帧往返转换，"
            "不做实际超分处理。未来将集成Real-ESRGAN等至少5种超分算法。"
        )
