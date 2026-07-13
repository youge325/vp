"""Parent-side rawvideo stage-worker chain runtime."""

from __future__ import annotations

import queue
from typing import Any

from app.planning import StagePlan
from app.planning.manifest import ResumeState
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.processing.streaming.worker_process_io import (
    DecodedFrameWriterConfig,
    decoded_frame_writer_session,
    drain_final_worker_output,
)
from app.processing.streaming.worker_processes import stage_worker_session


def run_worker_chain_runtime(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    plans: list[StageWorkerPlan],
    stage_plan: StagePlan,
    progress_callbacks: list[Any],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
    metrics: PipelineMetrics,
    python_executable: str | None = None,
) -> None:
    start_source_frame = int(resume_state.start_source_frame)
    with stage_worker_session(
        plans,
        progress_callbacks=progress_callbacks,
        error_queue=error_queue,
        stop_event=stop_event,
        python_executable=python_executable,
    ) as handles:
        with decoded_frame_writer_session(
            DecodedFrameWriterConfig(
                ffmpeg=ffmpeg,
                input_path=input_path,
                decode_config=decode_config,
                width=int(video_info["width"]),
                height=int(video_info["height"]),
                start_source_frame=start_source_frame,
                worker_stdin=handles[0].process.stdin,
                error_queue=error_queue,
                stop_event=stop_event,
            ),
            thread_name="vp-stage-worker-decode-writer",
        ):
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


__all__ = ["run_worker_chain_runtime"]
