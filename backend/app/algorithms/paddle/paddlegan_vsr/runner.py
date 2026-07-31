"""PaddleGAN VSR composition root.

Heavy Paddle imports remain lazy so normal environment checks and ONNX-only
runs never load Paddle.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.model_factory import build_paddlegan_model
from app.algorithms.paddle.paddlegan_vsr.sequence_executor import PaddleGanSequenceExecutor
from app.algorithms.paddle.paddlegan_vsr.tensorrt_cache import PaddleGanTensorRtPredictor
from app.algorithms.paddle.paddlegan_vsr.trace_observer import PaddleGanTraceObserver
from app.algorithms.paddle.paddlegan_vsr.weights import ensure_paddlegan_vsr_weights, get_spec


class PaddleGanVsrRunner:
    """Compose model loading, sequence execution, tracing, and optional TensorRT."""

    def __init__(self, *, model_id: str, num_frames: int, engine: str = "cuda"):
        self.model_id = model_id
        self.spec = get_spec(model_id)
        self.num_frames = int(num_frames)
        if self.num_frames < 1:
            raise ValueError("PaddleGAN VSR num_frames must be at least 1.")
        self.engine = (engine or "cuda").lower()
        if self.engine not in {"cuda", "tensorrt"}:
            raise ValueError(f"Unsupported PaddleGAN VSR engine: {engine!r}")
        self._paddle: Any | None = None
        self._model: Any | None = None
        self._trt_predictor: PaddleGanTensorRtPredictor | None = None

    def process_frames(
        self,
        input_frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        if not input_frames:
            return []
        paddle = self._ensure_paddle()
        trace = PaddleGanTraceObserver.from_environment()
        trace.begin(paddle)
        model = self._ensure_model()
        executor = PaddleGanSequenceExecutor(
            sequence_mode=self.spec.sequence_mode,
            num_frames=self.num_frames,
        )
        output_frames = executor.process(
            input_frames,
            paddle=paddle,
            run_tensor=lambda tensor: self._run_tensor(model, tensor),
            trace=trace,
            progress_callback=progress_callback,
        )
        trace.finish(
            paddle,
            model_id=self.model_id,
            sequence_mode=self.spec.sequence_mode,
            configured_num_frames=self.num_frames,
            input_frame_count=len(input_frames),
            output_frame_count=len(output_frames),
        )
        return output_frames

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        paddle = self._ensure_paddle()
        model = build_paddlegan_model(self.model_id)
        weight_path = ensure_paddlegan_vsr_weights(self.model_id)
        state = paddle.load(str(weight_path))
        if isinstance(state, dict) and "generator" in state:
            state = state["generator"]
        model.set_dict(state)
        model.eval()
        self._model = model
        return model

    def _ensure_paddle(self) -> Any:
        if self._paddle is not None:
            return self._paddle
        import paddle

        if paddle.device.is_compiled_with_cuda():
            paddle.set_device("gpu")
        self._paddle = paddle
        return paddle

    def _run_tensor(self, model: Any, tensor: Any) -> Any:
        if self.engine != "tensorrt":
            return model(tensor)
        if self._trt_predictor is None:
            self._trt_predictor = PaddleGanTensorRtPredictor(
                paddle=self._ensure_paddle(),
                model=model,
                model_id=self.model_id,
                sequence_mode=self.spec.sequence_mode,
                num_frames=self.num_frames,
            )
        return self._trt_predictor.run(tensor)


__all__ = ["PaddleGanVsrRunner"]
