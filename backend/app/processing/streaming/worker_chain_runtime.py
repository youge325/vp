"""Parent-side rawvideo stage-worker chain runtime."""

from __future__ import annotations

import queue
import threading

from app.processing.streaming.queues import EncodeQueue
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.processing.streaming.worker_process_io import (
    DecodedFrameWriterConfig,
    decoded_frame_writer_session,
    drain_final_worker_output,
)
from app.processing.streaming.worker_processes import stage_worker_session
from app.processing.streaming.worker_runtime_config import WorkerPipelineRuntimeConfig


def run_worker_chain_runtime(
    *,
    config: WorkerPipelineRuntimeConfig,
    plans: list[StageWorkerPlan],
    encode_queue: EncodeQueue,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    start_source_frame = int(config.resume_state.start_source_frame)
    with stage_worker_session(
        plans,
        progress_callbacks=config.progress_callbacks,
        error_queue=error_queue,
        stop_event=stop_event,
    ) as handles:
        with decoded_frame_writer_session(
            DecodedFrameWriterConfig(
                ffmpeg=config.ffmpeg,
                input_path=config.input_path,
                decode_config=config.decode_config,
                width=config.source_width,
                height=config.source_height,
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
                stage_plan=config.stage_plan,
                resume_state=config.resume_state,
                source_frames=config.source_frames,
                encode_queue=encode_queue,
                error_queue=error_queue,
                stop_event=stop_event,
                metrics=config.metrics,
            )


__all__ = ["run_worker_chain_runtime"]
