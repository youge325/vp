"""RGB sequence adapter for the inference-only Real-RawVSR BasicVSR model."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.algorithms.pytorch.real_rawvsr_basicvsr.assets import ensure_model_asset, variant_for_scale
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from app.generated.model_assets import REAL_RAWVSR_BASICVSR_CONTEXT_FRAMES
from app.planning.temporal_slicing import plan_temporal_slices

_MIN_SEQUENCE_FRAMES = 5
_MIN_SPATIAL_SIZE = 64


class RealRawVsrBasicVsr:
    def __init__(self, *, scale_factor: int, num_frames: int, engine: str, model_root: str) -> None:
        variant_for_scale(scale_factor)
        if num_frames < 1:
            raise ValueError("Real-RawVSR BasicVSR num_frames must be at least 1.")
        if engine != "cuda":
            raise ValueError(f"Real-RawVSR BasicVSR supports only CUDA; got {engine!r}.")
        self._scale_factor = scale_factor
        self._num_frames = num_frames
        self._engine = engine
        self._model_root = model_root
        self._torch: Any | None = None
        self._model: Any | None = None

    def _ensure_model(self) -> tuple[Any, Any]:
        if self._torch is None or self._model is None:
            from app.algorithms.pytorch.real_rawvsr_basicvsr.network import load_basicvsr_model

            model_path = ensure_model_asset(self._model_root, self._scale_factor)
            self._torch, self._model = load_basicvsr_model(scale=self._scale_factor, weight_path=str(model_path))
        return self._torch, self._model

    def process_frame_sequence(
        self,
        frames: list[Any],
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[Any]:
        return self.process_frames(frames, progress_callback=progress_callback)

    def process_frames(
        self,
        frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        if not frames:
            return []
        normalized = [_validate_rgb_frame(frame) for frame in frames]
        height, width = normalized[0].shape[:2]
        if any(frame.shape != normalized[0].shape for frame in normalized):
            raise ValueError("Real-RawVSR BasicVSR requires all input frames to have identical RGB dimensions.")
        padded_height = max(height, _MIN_SPATIAL_SIZE)
        padded_width = max(width, _MIN_SPATIAL_SIZE)
        spatially_padded = [_pad_spatial(frame, padded_height, padded_width) for frame in normalized]
        torch, model = self._ensure_model()
        output_height = height * self._scale_factor
        output_width = width * self._scale_factor
        results: list[np.ndarray] = []
        temporal_slices = plan_temporal_slices(
            len(spatially_padded),
            logical_chunk_frames=self._num_frames,
            context_frames=REAL_RAWVSR_BASICVSR_CONTEXT_FRAMES,
        )
        for temporal_slice in temporal_slices:
            read_end = temporal_slice.read_start + temporal_slice.read_count
            window, temporal_padding = _pad_temporal_sequence(spatially_padded[temporal_slice.read_start : read_end])
            stacked = np.stack(window, axis=0)
            tensor = (
                torch.from_numpy(stacked)
                .permute(0, 3, 1, 2)
                .unsqueeze(0)
                .to(
                    device="cuda",
                    dtype=torch.float32,
                )
                / 255.0
            )
            try:
                with torch.inference_mode():
                    output = model(tensor)
            except torch.cuda.OutOfMemoryError as exc:
                torch.cuda.empty_cache()
                raise ProcessError(
                    TaskErrorCode.PROCESS_FAILED,
                    "Real-RawVSR BasicVSR exhausted CUDA memory; lower the super-resolution frame chunk size.",
                    details={"numFrames": self._num_frames, "scaleFactor": self._scale_factor},
                ) from exc
            output_offset = temporal_padding + temporal_slice.output_offset
            logical = output[0, output_offset : output_offset + temporal_slice.logical_count]
            logical = logical[..., :output_height, :output_width]
            array = logical.clamp(0, 1).mul(255.0).round().to(dtype=torch.uint8).permute(0, 2, 3, 1).cpu().numpy()
            results.extend(np.ascontiguousarray(frame) for frame in array)
            if progress_callback is not None:
                progress_callback(
                    temporal_slice.logical_start + temporal_slice.logical_count,
                    len(normalized),
                )
        return results


def _validate_rgb_frame(frame: Any) -> np.ndarray:
    array = np.asarray(frame)
    if array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("Real-RawVSR BasicVSR input must be HxWx3 RGB uint8 frames.")
    return array


def _pad_temporal_sequence(frames: list[np.ndarray]) -> tuple[list[np.ndarray], int]:
    missing = max(_MIN_SEQUENCE_FRAMES - len(frames), 0)
    leading = missing // 2
    trailing = missing - leading
    return [frames[0]] * leading + frames + [frames[-1]] * trailing, leading


def _pad_spatial(frame: np.ndarray, height: int, width: int) -> np.ndarray:
    return np.pad(frame, ((0, height - frame.shape[0]), (0, width - frame.shape[1]), (0, 0)), mode="edge")


__all__ = ["RealRawVsrBasicVsr"]
