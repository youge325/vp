"""Rawvideo worker-chain runtime for streaming pipeline execution."""

from __future__ import annotations

import queue
import threading

from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.pipeline_context import StreamingPipelineContext
from app.processing.streaming.pipeline_raw_encoder import start_raw_encoder_thread
from app.processing.streaming.pipeline_rules import resolved_stream_fps
from app.processing.streaming.queues import (
    EncodeQueue,
    _ENCODE_END,
    _queue_put_nowait,
)
from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline
from app.processing.streaming.worker_runtime_config import WorkerPipelineRuntimeConfig


def run_raw_streaming_pipeline(
    *,
    context: StreamingPipelineContext,
) -> int:
    encode_queue: EncodeQueue = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    stream_fps = resolved_stream_fps(
        context.preflight.video_info.source_fps,
        context.preflight.stage_plan,
    )
    encoder_config = EncoderRuntimeConfig(
        ffmpeg=context.ffmpeg,
        encode_config=context.encode_config,
        manifest=context.manifest,
        width=context.preflight.output_width,
        height=context.preflight.output_height,
        fps=stream_fps,
        output_fps=context.output_fps,
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
        source_width=context.preflight.video_info.width,
        source_height=context.preflight.video_info.height,
        source_frames=context.preflight.video_info.source_frames,
        resume_state=context.resume_state,
        metrics=context.metrics,
    )

    encoder_thread = start_raw_encoder_thread(
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
    except BaseException:
        stop_event.set()
        _queue_put_nowait(encode_queue, _ENCODE_END)
        encoder_thread.join()
        raise

    encoder_thread.join()
    if not error_queue.empty():
        raise error_queue.get()

    return sum(segment.frame_count for segment in context.manifest.scan_completed_chunks())


__all__ = ["run_raw_streaming_pipeline"]
