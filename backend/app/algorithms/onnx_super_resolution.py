"""Single-frame ONNX image-to-image super-resolution."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.utils.onnx_models import create_onnx_session, resolve_onnx_model_path


class OnnxSuperResolution:
    def __init__(
        self,
        *,
        sr_algorithm: str,
        onnx_model: str | None,
        model_dir: str,
        engine: str,
    ) -> None:
        self._algorithm_name = sr_algorithm
        self._onnx_model = onnx_model
        self._model_dir = model_dir
        self._engine = engine
        self._session = None
        self._input_name = ""
        self._output_name = ""

    def process_frame(self, frame: Any) -> Any:
        session = self._ensure_onnx_session()
        input_tensor = np.asarray(frame, dtype=np.float32)
        if input_tensor.ndim != 4 or input_tensor.shape[0] != 1 or input_tensor.shape[1] != 3:
            raise RuntimeError("ONNX super-resolution input must be NCHW RGB float32 with shape (1, 3, H, W).")
        output_tensor = np.asarray(
            session.run([self._output_name], {self._input_name: input_tensor})[0],
            dtype=np.float32,
        )
        self._validate_output_tensor(output_tensor)
        return np.clip(output_tensor, 0.0, 1.0).astype(np.float32)

    def _ensure_onnx_session(self) -> Any:
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

    @staticmethod
    def _validate_output_tensor(output_tensor: np.ndarray) -> None:
        if output_tensor.ndim != 4 or output_tensor.shape[0] != 1 or output_tensor.shape[1] != 3:
            raise RuntimeError("ONNX super-resolution output must be NCHW RGB float32 with shape (1, 3, H, W).")
