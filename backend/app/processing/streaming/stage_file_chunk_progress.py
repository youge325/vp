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
    def adapter(current: int, *_worker_progress: Any, **kwargs: Any) -> None:
        if step.algorithm_type == "frame_interpolation":
            current_value = min(chunk.input_start_frame + max(int(current), 0), total)
        else:
            current_value = min(chunk.input_start_frame + max(int(current), 0), total)
        callback(current_value, total, **kwargs)

    return adapter


__all__ = ["chunk_progress_adapter"]
