"""Sequence scheduling for PaddleGAN video super-resolution."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from app.algorithms.paddle.paddlegan_vsr.tensor_codec import (
    frames_to_tensor,
    image_tensor_to_frames,
    sequence_tensor_to_frames,
)
from app.catalog.paddlegan_models import PaddleGanSequenceMode


class ChunkTracePort(Protocol):
    """Trace capability consumed by the sequence executor."""

    def record_chunk(self, paddle: Any, *, tensor: Any, output: Any, frame_count: int) -> None: ...


@dataclass(frozen=True, slots=True)
class PaddleGanSequenceExecutor:
    """Apply one tensor inference function using the model's declared scheduling mode."""

    sequence_mode: PaddleGanSequenceMode
    num_frames: int

    def __post_init__(self) -> None:
        if self.num_frames < 1:
            raise ValueError("PaddleGAN VSR num_frames must be at least 1.")

    def process(
        self,
        input_frames: Sequence[np.ndarray],
        *,
        paddle: Any,
        run_tensor: Callable[[Any], Any],
        trace: ChunkTracePort,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        if self.sequence_mode == "window":
            batches = (
                [input_frames[i] for i in _edvr_neighbor_indexes(index, len(input_frames))]
                for index in range(len(input_frames))
            )
            output_to_frames = image_tensor_to_frames
            select_last_output = False
        else:
            batches = (
                list(input_frames[start : start + self.num_frames])
                for start in range(0, len(input_frames), self.num_frames)
            )
            output_to_frames = sequence_tensor_to_frames
            select_last_output = True

        total = len(input_frames)
        output_frames: list[np.ndarray] = []
        with paddle.no_grad():
            for batch in batches:
                tensor = frames_to_tensor(batch, paddle)
                output = run_tensor(tensor)
                if select_last_output and isinstance(output, (list, tuple)):
                    output = output[-1]
                trace.record_chunk(paddle, tensor=tensor, output=output, frame_count=len(batch))
                output_frames.extend(output_to_frames(output))
                if progress_callback is not None:
                    progress_callback(min(len(output_frames), total), total)
        return output_frames


def _edvr_neighbor_indexes(index: int, length: int, window_size: int = 5) -> list[int]:
    if length <= 0:
        return []
    radius = window_size // 2
    return [min(max(index + offset, 0), length - 1) for offset in range(-radius, radius + 1)]


__all__ = ["ChunkTracePort", "PaddleGanSequenceExecutor"]
