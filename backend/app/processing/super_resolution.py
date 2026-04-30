"""超分辨率算法实现。"""

from typing import Any

import numpy as np

from app.algorithms.base import IAlgorithm
from app.algorithms.onnx_models import resolve_onnx_model_path
from app.algorithms.tensor_backend import ITensorBackend
from app.config import settings


class SuperResolutionAlgorithm(IAlgorithm):
    """
    超分辨率算法占位实现。

    当前为无操作实现：接收 Tensor 后原样返回。
    未来实现将：
    - 使用 SR 模型（Real-ESRGAN 等）提升帧分辨率
    - 支持可配置的放大倍率（2x, 4x）
    - 支持至少 5 种不同的超分算法
    """

    def __init__(self, tensor_backend: ITensorBackend = None, **kwargs):
        self._tensor_backend = tensor_backend
        self._scale_factor = kwargs.get("scale_factor", 2.0)
        self._algorithm_name = kwargs.get("sr_algorithm", "placeholder")
        self._onnx_model = kwargs.get("onnx_model")
        self._model_dir = kwargs.get("model_dir", settings.RIFE_MODEL_DIR)
        self._engine = kwargs.get("engine", "cuda")
        self._session = None
        self._input_name = ""
        self._output_name = ""

    def process_frame(self, frame: Any, **kwargs) -> Any:
        """处理单帧；ONNX 后端运行 image-to-image 超分，否则保持占位行为。"""
        if self._backend_name() != "onnx":
            return frame

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

        import onnxruntime as ort

        model_path = resolve_onnx_model_path("super_resolution", self._onnx_model, self._model_dir)
        if self._engine == "tensorrt":
            providers = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
        elif self._engine == "cuda":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        else:
            providers = ort.get_available_providers()
        session = ort.InferenceSession(str(model_path), providers=providers)
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

    def process_frame_batch(self, frames: list[Any], **kwargs) -> list[Any]:
        """逐帧处理批量输入。"""
        return [self.process_frame(frame, **kwargs) for frame in frames]

    def get_name(self) -> str:
        if self._backend_name() == "onnx":
            return f"超分辨率算法(ONNX {self._onnx_model or '未选择'})"
        return "超分辨率算法(占位)"

    def validate(self) -> bool:
        """验证超分算法配置。"""
        if self._backend_name() == "onnx":
            return bool(self._onnx_model)
        return True

    def get_description(self) -> str:
        if self._backend_name() == "onnx":
            return f"基于 ONNX Runtime 的 {self._scale_factor:g}x 视频超分辨率处理。"
        return (
            "视频超分辨率处理占位算法。当前实现：帧→Tensor→帧往返转换，"
            "不做实际超分处理。未来将集成Real-ESRGAN等至少5种超分算法。"
        )
