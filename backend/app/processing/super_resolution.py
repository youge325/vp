"""超分辨率算法实现。"""

from typing import Any

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner
from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from app.catalog.stage_descriptors import PADDLEGAN_STAGE_DESCRIPTORS, StageDescriptor
from app.utils.onnx_models import create_onnx_session, resolve_onnx_model_path
from app.utils.model_metrics import get_paddlegan_model_detail


def _paddlegan_algorithm_metadata(model_id: str, descriptor: StageDescriptor) -> dict[str, Any]:
    spec = PADDLEGAN_VSR_SPECS[model_id]
    return {
        "name": model_id,
        "family": descriptor.model_kind,
        "tensorBackends": sorted(descriptor.supported_backends),
        "models": ["x4"],
        "scaleFactors": [descriptor.fixed_scale_factor],
        "fixedScaleFactor": descriptor.fixed_scale_factor,
        "defaultNumFrames": spec.default_num_frames,
        "inputFrameMode": "fixed_window" if spec.sequence_mode == "window" else "editable_chunk",
        "modelDetails": [get_paddlegan_model_detail(model_id)],
    }


SUPPORTED_ALGORITHMS: list[dict[str, Any]] = [
    # ``tensorBackends`` 显式声明每个算法支持的 tensor 后端。
    {
        "name": "placeholder",
        "family": "onnx_super_resolution",
        "tensorBackends": ["onnx"],
        "models": [],
        "inputFrameMode": "none",
    },
    *[
        _paddlegan_algorithm_metadata(model_id, descriptor)
        for model_id, descriptor in PADDLEGAN_STAGE_DESCRIPTORS.items()
    ],
]


class OnnxSuperResolution:
    """Single-frame ONNX image-to-image super-resolution."""

    def __init__(self, **kwargs: Any):
        self._scale_factor = kwargs.get("scale_factor", 2.0)
        self._algorithm_name = kwargs.get("sr_algorithm", "placeholder")
        self._onnx_model = kwargs.get("onnx_model")
        self._model_dir = kwargs.get("model_dir", "")
        self._engine = kwargs.get("engine", "cuda")
        self._session = None
        self._input_name = ""
        self._output_name = ""

    def process_frame(self, frame: Any, **_kwargs) -> Any:
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


class PaddleGanVideoSuperResolution:
    """Frame-sequence PaddleGAN video super-resolution."""

    def __init__(self, **kwargs: Any):
        self._algorithm_name = str(kwargs.get("sr_algorithm") or "")
        if self._algorithm_name not in PADDLEGAN_STAGE_DESCRIPTORS:
            raise ValueError(f"Unknown PaddleGAN VSR algorithm: {self._algorithm_name}")
        raw_num_frames = kwargs.get("num_frames", kwargs.get("numFrames"))
        if raw_num_frames is None:
            raise ValueError("PaddleGAN VSR num_frames is required.")
        self._num_frames = int(raw_num_frames)
        if self._num_frames < 1:
            raise ValueError("PaddleGAN VSR num_frames must be at least 1.")
        self._engine = str(kwargs.get("engine") or "cuda")
        self._runner: PaddleGanVsrRunner | None = None

    def _ensure_runner(self) -> PaddleGanVsrRunner:
        if self._runner is None:
            self._runner = PaddleGanVsrRunner(
                model_id=self._algorithm_name,
                num_frames=self._num_frames,
                engine=self._engine,
            )
        return self._runner

    def process_frame_sequence(self, frames: list[Any], **kwargs: Any) -> list[Any]:
        return self._ensure_runner().process_frames(
            frames,
            progress_callback=kwargs.get("progress_callback"),
        )


__all__ = [
    "OnnxSuperResolution",
    "PaddleGanVideoSuperResolution",
    "SUPPORTED_ALGORITHMS",
]
