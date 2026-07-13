"""Parent-side rawvideo worker pipeline helpers."""

from __future__ import annotations

import queue
import threading
from typing import Any

from app.planning import StagePlan
from app.planning.manifest import ResumeState
from app.processing.streaming.worker_chain_runtime import run_worker_chain_runtime
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import StreamEnd, _ENCODE_END, _queue_put, _queue_put_nowait
from app.processing.streaming.worker_plans import build_stage_worker_plans


def _enqueue_stream_end(*, encode_queue: queue.Queue[Any], stop_event: threading.Event, source_frames: int) -> None:
    _queue_put(encode_queue, StreamEnd(next_source_frame=int(source_frames)), stop_event)


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
) -> None:
    """Run algorithm stages as isolated rawvideo subprocesses.

    The function pushes ``EncodedFrame`` / ``SegmentBoundary`` / ``StreamEnd``
    packets into ``encode_queue`` for the existing encoder worker.
    """
    start_source_frame = int(resume_state.start_source_frame)
    remaining_source_frames = max(int(video_info["source_frames"]) - start_source_frame, 0)
    if remaining_source_frames <= 0:
        _enqueue_stream_end(
            encode_queue=encode_queue,
            stop_event=stop_event,
            source_frames=int(video_info["source_frames"]),
        )
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
    )

    if not error_queue.empty():
        _queue_put_nowait(encode_queue, _ENCODE_END)
        return
    _enqueue_stream_end(
        encode_queue=encode_queue,
        stop_event=stop_event,
        source_frames=int(video_info["source_frames"]),
    )


__all__ = ["run_stage_worker_pipeline"]
