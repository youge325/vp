"""Shared five-frame RGB adapter for fixed-window Real-RawVSR models."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
import numpy as np

from app.algorithms.pytorch.real_rawvsr.sequence_adapter import ModelLoadSpec, ModelLoader, RealRawVsrSequenceAdapter


class RealRawVsrFixedWindow(RealRawVsrSequenceAdapter):
    def __init__(
        self,
        *,
        spec: ModelLoadSpec,
        model_loader: ModelLoader,
    ) -> None:
        super().__init__(spec, model_loader)
        family = self._family
        if family.input_frame_mode != "fixed_window":
            raise ValueError(f"{family.display_name} is not a fixed-window model.")
        if family.default_num_frames != family.temporal_context_frames * 2 + 1:
            raise ValueError(f"{family.display_name} has an invalid temporal asset contract.")
        self._window_frames = family.default_num_frames
        self._context_frames = family.temporal_context_frames

    def _process_prepared(
        self,
        prepared: Any,
        torch: Any,
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[np.ndarray]:
        results: list[np.ndarray] = []
        total = len(prepared.frames)
        for index in range(total):
            window = [
                prepared.frames[position] for position in _centered_window_indices(index, total, self._context_frames)
            ]
            if len(window) != self._window_frames:
                raise RuntimeError("Real-RawVSR fixed-window projection produced an invalid window.")
            tensor = self._codec.to_cuda(torch, window)
            prediction = self._run_model(
                tensor,
                oom_message=f"{self._family.display_name} x{self._scale_factor} exhausted CUDA memory; "
                "lower the input resolution or select a lighter super-resolution algorithm.",
                details={"algorithm": self._algorithm_id, "scaleFactor": self._scale_factor},
            )
            if isinstance(prediction, tuple):
                prediction = prediction[0]
            results.extend(self._codec.to_frames(torch, prediction, prepared))
            if progress_callback is not None:
                progress_callback(index + 1, total)
        return results


def _centered_window_indices(index: int, total: int, context: int) -> tuple[int, ...]:
    if total < 1 or not 0 <= index < total or context < 0:
        raise ValueError("Centered temporal window bounds are invalid.")
    return tuple(min(max(index + delta, 0), total - 1) for delta in range(-context, context + 1))


__all__ = ["RealRawVsrFixedWindow"]
