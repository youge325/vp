"""Rawvideo worker-chain runtime for streaming pipeline execution."""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_encoder import start_raw_encoder_thread
from app.processing.streaming.pipeline_rules import resolved_stream_fps
from app.processing.streaming.queues import (
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _ENCODE_END,
    _queue_put_nowait,
)
from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline
from app.utils.ffmpeg import FFmpegWrapper


def run_raw_streaming_pipeline(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    video_info: dict[str, Any],
    output_width: int,
    output_height: int,
    resume_state: ResumeState,
    segment_frames: int,
    output_path: str,
    output_fps: float | None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
) -> int:
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    stream_fps = resolved_stream_fps(video_info["source_fps"], stage_plan)

    encoder_thread = start_raw_encoder_thread(
        ffmpeg=ffmpeg,
        encode_config=encode_config,
        manifest=manifest,
        output_width=output_width,
        output_height=output_height,
        stream_fps=stream_fps,
        output_fps=output_fps,
        segment_frames=segment_frames,
        resume_state=resume_state,
        output_path=output_path,
        encode_progress_callback=encode_progress_callback,
        metrics=metrics,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
    )
    try:
        run_stage_worker_pipeline(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            stage_plan=stage_plan,
            tensor_backend_name=tensor_backend_name,
            progress_callbacks=progress_callbacks,
            video_info=video_info,
            resume_state=resume_state,
            encode_queue=encode_queue,
            error_queue=error_queue,
            stop_event=stop_event,
            metrics=metrics,
        )
    except BaseException:
        stop_event.set()
        _queue_put_nowait(encode_queue, _ENCODE_END)
        encoder_thread.join()
        raise

    encoder_thread.join()
    if not error_queue.empty():
        raise error_queue.get()

    return sum(segment.frame_count for segment in manifest.scan_completed_chunks())


__all__ = ["run_raw_streaming_pipeline"]
