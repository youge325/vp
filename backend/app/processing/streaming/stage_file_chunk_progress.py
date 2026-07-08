"""Progress mapping helpers for file-backed stage chunks."""

from __future__ import annotations

from typing import Any

from app.planning import ProcessingStep
from app.processing.streaming.worker_plans import StageChunkPlan


def chunk_progress_adapter(
    step: ProcessingStep,
    *,
    chunk: StageChunkPlan,
    total: int,
    callback: Any,
) -> Any:
    def adapter(current: int, progress_total: int, **kwargs: Any) -> None:
        del progress_total
        if step.algorithm_type == "frame_interpolation":
            current_value = min(chunk.input_start_frame + max(int(current), 0), total)
        else:
            current_value = min(stage_chunk_output_start(step, chunk) + max(int(current), 0), total)
        callback(current_value, total, **kwargs)

    return adapter


def stage_chunk_output_start(step: ProcessingStep, chunk: StageChunkPlan) -> int:
    if step.algorithm_type != "frame_interpolation":
        return chunk.input_start_frame
    multi = int(step.algorithm_kwargs.get("multi") or 2)
    if chunk.input_start_frame <= 0:
        return 0
    return chunk.input_start_frame + chunk.input_start_frame * (multi - 1)


__all__ = [
    "chunk_progress_adapter",
    "stage_chunk_output_start",
]
