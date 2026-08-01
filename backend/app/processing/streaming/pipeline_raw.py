"""Rawvideo worker-chain runtime for streaming pipeline execution."""

from __future__ import annotations

import queue
import threading
import time

from app.generated.protocol_constants import TERMINATION_REAP_TIMEOUT_MS
from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.error_channel import create_error_queue, take_first_error
from app.processing.streaming.pipeline_context import StreamingPipelineContext
from app.processing.streaming.pipeline_raw_encoder import start_raw_encoder_thread
from app.processing.streaming.queues import EncodeQueue
from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline
from app.processing.streaming.worker_runtime_config import WorkerPipelineRuntimeConfig


def run_raw_streaming_pipeline(
    *,
    context: StreamingPipelineContext,
) -> int:
    encode_queue: EncodeQueue = queue.Queue(maxsize=8)
    error_queue = create_error_queue()
    stop_event = threading.Event()
    stage_plan = context.preflight.stage_plan
    output_width, output_height = stage_plan.output_dimensions
    encoder_config = EncoderRuntimeConfig(
        ffmpeg=context.ffmpeg,
        encode_config=context.encode_config,
        manifest=context.manifest,
        width=output_width,
        height=output_height,
        fps=stage_plan.stream_fps,
        output_fps=stage_plan.encoder_fps_override,
        segment_frames=context.preflight.segment_frames,
        resume_state=context.resume_state,
        output_path=context.output_path,
        encode_progress_callback=context.encode_progress_callback,
        metrics=context.metrics,
    )
    worker_config = WorkerPipelineRuntimeConfig(
        ffmpeg=context.ffmpeg,
        input_path=context.input_path,
        decode_config=context.decode_config,
        stage_plan=context.preflight.stage_plan,
        progress_callbacks=context.progress_callbacks,
        resume_state=context.resume_state,
        metrics=context.metrics,
        worker_log_sink=context.worker_log_sink,
    )

    encoder_owner = start_raw_encoder_thread(
        config=encoder_config,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
    )
    try:
        run_stage_worker_pipeline(
            config=worker_config,
            encode_queue=encode_queue,
            error_queue=error_queue,
            stop_event=stop_event,
        )
    except BaseException as exc:
        cleanup_deadline = time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000
        if not encoder_owner.abort(deadline=cleanup_deadline):
            exc.add_note("Encoder cleanup did not finish before the termination deadline.")
        raise

    cleanup_deadline = time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000
    if not encoder_owner.finish(deadline=cleanup_deadline):
        raise RuntimeError("Encoder did not exit before the cleanup deadline.")
    if error := take_first_error(error_queue):
        raise error

    return sum(segment.frame_count for segment in context.manifest.scan_completed_chunks())


__all__ = ["run_raw_streaming_pipeline"]
