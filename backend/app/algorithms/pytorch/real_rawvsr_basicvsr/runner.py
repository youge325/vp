"""RGB sequence adapter for the inference-only Real-RawVSR BasicVSR model."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import numpy as np

from app.algorithms.pytorch.real_rawvsr.rgb_frames import frames_to_cuda_tensor, prepare_rgb_frames
from app.algorithms.pytorch.real_rawvsr.sequence_adapter import RealRawVsrSequenceAdapter
from app.planning.temporal_slicing import plan_temporal_slices

_MIN_SEQUENCE_FRAMES = 5
_MIN_SPATIAL_SIZE = 64


class RealRawVsrBasicVsr(RealRawVsrSequenceAdapter):
    def __init__(
        self,
        *,
        algorithm_id: str,
        scale_factor: int,
        num_frames: int,
        engine: str,
        model_root: str,
    ) -> None:
        super().__init__(
            algorithm_id=algorithm_id,
            scale_factor=scale_factor,
            engine=engine,
            model_root=model_root,
        )
        if num_frames < 1:
            raise ValueError("Real-RawVSR BasicVSR num_frames must be at least 1.")
        self._context_frames = self._family.temporal_context_frames
        self._num_frames = num_frames

    def _ensure_model(self) -> tuple[object, object]:
        from app.algorithms.pytorch.real_rawvsr_basicvsr.network import load_basicvsr_model

        return self._load_model(lambda scale, path: load_basicvsr_model(scale=scale, weight_path=path))

    def process_frames(
        self,
        frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        prepared = prepare_rgb_frames(frames, self._family.display_name, minimum_size=_MIN_SPATIAL_SIZE)
        if prepared is None:
            return []
        torch, _model = self._ensure_model()
        output_height = prepared.height * self._scale_factor
        output_width = prepared.width * self._scale_factor
        results: list[np.ndarray] = []
        temporal_slices = plan_temporal_slices(
            len(prepared.frames),
            logical_chunk_frames=self._num_frames,
            context_frames=self._context_frames,
        )
        for temporal_slice in temporal_slices:
            read_end = temporal_slice.read_start + temporal_slice.read_count
            window, temporal_padding = _pad_temporal_sequence(
                list(prepared.frames[temporal_slice.read_start : read_end])
            )
            tensor = frames_to_cuda_tensor(torch, window)
            output = self._run_model(
                tensor,
                oom_message="Real-RawVSR BasicVSR exhausted CUDA memory; lower the super-resolution frame chunk size.",
                details={"numFrames": self._num_frames, "scaleFactor": self._scale_factor},
            )
            output_offset = temporal_padding + temporal_slice.output_offset
            logical = output[0, output_offset : output_offset + temporal_slice.logical_count]
            logical = logical[..., :output_height, :output_width]
            array = logical.clamp(0, 1).mul(255.0).round().to(dtype=torch.uint8).permute(0, 2, 3, 1).cpu().numpy()
            results.extend(np.ascontiguousarray(frame) for frame in array)
            if progress_callback is not None:
                progress_callback(
                    temporal_slice.logical_start + temporal_slice.logical_count,
                    len(prepared.frames),
                )
        return results


def _pad_temporal_sequence(frames: list[np.ndarray]) -> tuple[list[np.ndarray], int]:
    missing = max(_MIN_SEQUENCE_FRAMES - len(frames), 0)
    leading = missing // 2
    trailing = missing - leading
    return [frames[0]] * leading + frames + [frames[-1]] * trailing, leading


__all__ = ["RealRawVsrBasicVsr"]
