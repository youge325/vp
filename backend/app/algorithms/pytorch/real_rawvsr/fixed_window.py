"""Shared five-frame RGB adapter for fixed-window Real-RawVSR models."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import numpy as np

from app.algorithms.pytorch.real_rawvsr.rgb_frames import frames_to_cuda_tensor, prepare_rgb_frames
from app.algorithms.pytorch.real_rawvsr.sequence_adapter import ModelLoader, RealRawVsrSequenceAdapter

_SPATIAL_MODULO = 16


class RealRawVsrFixedWindow(RealRawVsrSequenceAdapter):
    def __init__(
        self,
        *,
        algorithm_id: str,
        scale_factor: int,
        num_frames: int,
        engine: str,
        model_root: str,
        model_loader: ModelLoader,
    ) -> None:
        super().__init__(
            algorithm_id=algorithm_id,
            scale_factor=scale_factor,
            engine=engine,
            model_root=model_root,
        )
        family = self._family
        if family.input_frame_mode != "fixed_window":
            raise ValueError(f"{family.display_name} is not a fixed-window model.")
        if num_frames != family.default_num_frames:
            raise ValueError(f"{family.display_name} requires exactly {family.default_num_frames} frames per window.")
        if family.default_num_frames != family.temporal_context_frames * 2 + 1:
            raise ValueError(f"{family.display_name} has an invalid temporal asset contract.")
        self._window_frames = family.default_num_frames
        self._context_frames = family.temporal_context_frames
        self._model_loader = model_loader

    def _ensure_model(self) -> tuple[object, object]:
        return self._load_model(self._model_loader)

    def process_frames(
        self,
        frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        prepared = prepare_rgb_frames(
            frames,
            self._family.display_name,
            minimum_size=_SPATIAL_MODULO,
            spatial_modulo=_SPATIAL_MODULO,
        )
        if prepared is None:
            return []
        torch, _model = self._ensure_model()
        results: list[np.ndarray] = []
        total = len(prepared.frames)
        for index in range(total):
            window = [
                prepared.frames[position] for position in _centered_window_indices(index, total, self._context_frames)
            ]
            if len(window) != self._window_frames:
                raise RuntimeError("Real-RawVSR fixed-window projection produced an invalid window.")
            tensor = frames_to_cuda_tensor(torch, window)
            prediction = self._run_model(
                tensor,
                oom_message=f"{self._family.display_name} x{self._scale_factor} exhausted CUDA memory; "
                "lower the input resolution or select a lighter super-resolution algorithm.",
                details={"algorithm": self._algorithm_id, "scaleFactor": self._scale_factor},
            )
            if isinstance(prediction, tuple):
                prediction = prediction[0]
            output = prediction[
                0,
                :,
                : prepared.height * self._scale_factor,
                : prepared.width * self._scale_factor,
            ]
            array = output.clamp(0, 1).mul(255.0).round().to(dtype=torch.uint8).permute(1, 2, 0).cpu().numpy()
            results.append(np.ascontiguousarray(array))
            if progress_callback is not None:
                progress_callback(index + 1, total)
        return results


def _centered_window_indices(index: int, total: int, context: int) -> tuple[int, ...]:
    if total < 1 or not 0 <= index < total or context < 0:
        raise ValueError("Centered temporal window bounds are invalid.")
    return tuple(min(max(index + delta, 0), total - 1) for delta in range(-context, context + 1))


__all__ = ["RealRawVsrFixedWindow"]
