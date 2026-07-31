"""Parent-side rawvideo stage-worker chain runtime."""

from __future__ import annotations

import queue
import threading

from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.queues import EncodeQueue
from app.processing.streaming.worker_process_io import DecodedFrameWriterConfig, drain_final_worker_output
from app.processing.streaming.worker_processes import stage_worker_session
from app.processing.streaming.worker_runtime_config import WorkerPipelineRuntimeConfig


def run_worker_chain_runtime(
    *,
    config: WorkerPipelineRuntimeConfig,
    configs: list[StageWorkerConfig],
    encode_queue: EncodeQueue,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    start_source_frame = int(config.resume_state.start_source_frame)
    with stage_worker_session(
        configs,
        progress_callbacks=config.progress_callbacks,
        error_queue=error_queue,
        stop_event=stop_event,
        worker_log_sink=config.worker_log_sink,
    ) as group:
        group.start_decoded_frame_writer(
            DecodedFrameWriterConfig(
                ffmpeg=config.ffmpeg,
                input_path=config.input_path,
                decode_config=config.decode_config,
                width=config.source_width,
                height=config.source_height,
                start_source_frame=start_source_frame,
                worker_stdin=group.handles[0].process.stdin,
                error_queue=error_queue,
                stop_event=stop_event,
            ),
            thread_name="vp-stage-worker-decode-writer",
        )
        drain_final_worker_output(
            final_stdout=group.handles[-1].process.stdout,
            final_config=configs[-1],
            stage_plan=config.stage_plan,
            resume_state=config.resume_state,
            source_frames=config.source_frames,
            encode_queue=encode_queue,
            error_queue=error_queue,
            stop_event=stop_event,
            metrics=config.metrics,
        )


__all__ = ["run_worker_chain_runtime"]
