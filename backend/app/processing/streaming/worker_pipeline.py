"""Parent-side rawvideo worker pipeline helpers."""

from __future__ import annotations

import queue
from typing import Any

from app.planning import StagePlan
from app.planning.manifest import ResumeState
from app.processing.streaming.worker_chain_runtime import run_worker_chain_runtime
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    StreamEnd,
    _ENCODE_END,
    _queue_put,
    _queue_put_nowait,
)
from app.processing.streaming.stage_file_pipeline import run_stage_file_pipeline
from app.processing.streaming.worker_plans import (
    StageChunkPlan,
    StageWorkerPlan,
    boundary_schedule_for_stage_plan,
    build_stage_chunk_plans,
    build_stage_worker_plans,
)
from app.processing.streaming.worker_process_events import parse_stage_event_line


def run_stage_worker_pipeline(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Any],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
    metrics: PipelineMetrics,
    python_executable: str | None = None,
) -> None:
    """Run algorithm stages as isolated rawvideo subprocesses.

    The function pushes ``EncodedFrame`` / ``SegmentBoundary`` / ``StreamEnd``
    packets into ``encode_queue`` for the existing encoder worker.
    """
    start_source_frame = int(resume_state.start_source_frame)
    remaining_source_frames = max(int(video_info["source_frames"]) - start_source_frame, 0)
    if remaining_source_frames <= 0:
        _queue_put(encode_queue, StreamEnd(next_source_frame=int(video_info["source_frames"])), stop_event)
        return

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
        source_width=int(video_info["width"]),
        source_height=int(video_info["height"]),
        source_frame_count=remaining_source_frames,
    )
    if not plans:
        raise RuntimeError("Worker pipeline requires at least one processing stage.")

    run_worker_chain_runtime(
        ffmpeg=ffmpeg,
        input_path=input_path,
        decode_config=decode_config,
        plans=plans,
        stage_plan=stage_plan,
        progress_callbacks=progress_callbacks,
        video_info=video_info,
        resume_state=resume_state,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=metrics,
        python_executable=python_executable,
    )

    if not error_queue.empty():
        _queue_put_nowait(encode_queue, _ENCODE_END)
        return
    _queue_put(encode_queue, StreamEnd(next_source_frame=int(video_info["source_frames"])), stop_event)


__all__ = [
    "StageChunkPlan",
    "StageWorkerPlan",
    "boundary_schedule_for_stage_plan",
    "build_stage_chunk_plans",
    "build_stage_worker_plans",
    "parse_stage_event_line",
    "run_stage_file_pipeline",
    "run_stage_worker_pipeline",
]
