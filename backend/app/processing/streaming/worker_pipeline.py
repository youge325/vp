"""Parent-side rawvideo worker pipeline helpers."""

from __future__ import annotations

from pathlib import Path
import queue
import sys
import tempfile
import threading
from typing import Any

from app.planning import StagePlan
from app.planning.manifest import ResumeState
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
from app.processing.streaming.worker_processes import (
    close_pipe,
    drain_final_worker_output,
    parse_stage_event_line,
    read_worker_stderr,
    spawn_stage_workers,
    wait_for_workers,
    write_decoded_frames_to_worker,
)


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
    stop_event: threading.Event,
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

    with tempfile.TemporaryDirectory(prefix="vp-stage-workers-") as config_dir:
        handles = spawn_stage_workers(
            plans,
            config_dir=Path(config_dir),
            python_executable=python_executable or sys.executable,
        )
        stderr_threads = [
            threading.Thread(
                target=read_worker_stderr,
                name=f"vp-stage-worker-stderr-{handle.plan.config.stage_index}",
                args=(handle, progress_callbacks, error_queue, stop_event),
                daemon=True,
            )
            for handle in handles
        ]
        for thread in stderr_threads:
            thread.start()

        decode_thread = threading.Thread(
            target=write_decoded_frames_to_worker,
            name="vp-stage-worker-decode-writer",
            kwargs={
                "ffmpeg": ffmpeg,
                "input_path": input_path,
                "decode_config": decode_config,
                "video_info": video_info,
                "start_source_frame": start_source_frame,
                "worker_stdin": handles[0].process.stdin,
                "error_queue": error_queue,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        decode_thread.start()

        try:
            drain_final_worker_output(
                final_stdout=handles[-1].process.stdout,
                final_plan=plans[-1],
                stage_plan=stage_plan,
                resume_state=resume_state,
                source_frames=int(video_info["source_frames"]),
                encode_queue=encode_queue,
                error_queue=error_queue,
                stop_event=stop_event,
                metrics=metrics,
            )
        finally:
            decode_thread.join()
            for handle in handles:
                close_pipe(handle.process.stdin)
                close_pipe(handle.process.stdout)
            wait_for_workers(handles, error_queue)
            for thread in stderr_threads:
                thread.join(timeout=1)

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
