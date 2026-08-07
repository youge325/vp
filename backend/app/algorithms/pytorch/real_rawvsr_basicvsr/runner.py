"""RGB sequence adapter for the inference-only Real-RawVSR BasicVSR model."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
import numpy as np

from app.algorithms.pytorch.real_rawvsr.sequence_adapter import ModelLoadSpec, ModelLoader, RealRawVsrSequenceAdapter
from app.planning.temporal_slicing import plan_temporal_slices


class RealRawVsrBasicVsr(RealRawVsrSequenceAdapter):
    def __init__(
        self,
        *,
        spec: ModelLoadSpec,
        model_loader: ModelLoader,
    ) -> None:
        super().__init__(spec, model_loader)
        if spec.family.input_frame_mode != "editable_chunk":
            raise ValueError(f"{spec.family.display_name} is not an editable-chunk model.")
        self._context_frames = self._family.temporal_context_frames
        self._num_frames = spec.num_frames
        self._minimum_sequence_frames = self._context_frames * 2 + 1

    def _process_prepared(
        self,
        prepared: Any,
        torch: Any,
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[np.ndarray]:
        results: list[np.ndarray] = []
        temporal_slices = plan_temporal_slices(
            len(prepared.frames),
            logical_chunk_frames=self._num_frames,
            context_frames=self._context_frames,
        )
        for temporal_slice in temporal_slices:
            read_end = temporal_slice.read_start + temporal_slice.read_count
            window, temporal_padding = _pad_temporal_sequence(
                list(prepared.frames[temporal_slice.read_start : read_end]),
                minimum_frames=self._minimum_sequence_frames,
            )
            tensor = self._codec.to_cuda(torch, window)
            output = self._run_model(
                tensor,
                oom_message="Real-RawVSR BasicVSR exhausted CUDA memory; lower the super-resolution frame chunk size.",
                details={"numFrames": self._num_frames, "scaleFactor": self._scale_factor},
            )
            output_offset = temporal_padding + temporal_slice.output_offset
            logical = output[0, output_offset : output_offset + temporal_slice.logical_count]
            results.extend(self._codec.to_frames(torch, logical.unsqueeze(0), prepared))
            if progress_callback is not None:
                progress_callback(
                    temporal_slice.logical_start + temporal_slice.logical_count,
                    len(prepared.frames),
                )
        return results


def _pad_temporal_sequence(frames: list[np.ndarray], *, minimum_frames: int) -> tuple[list[np.ndarray], int]:
    missing = max(minimum_frames - len(frames), 0)
    leading = missing // 2
    trailing = missing - leading
    return [frames[0]] * leading + frames + [frames[-1]] * trailing, leading


__all__ = ["RealRawVsrBasicVsr"]
