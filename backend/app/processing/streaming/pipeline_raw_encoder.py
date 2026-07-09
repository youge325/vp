"""Raw pipeline encoder thread lifecycle."""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.encoder_worker import run_encoder_worker
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd
from app.utils.ffmpeg import FFmpegWrapper


def start_raw_encoder_thread(
    *,
    ffmpeg: FFmpegWrapper,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    output_width: int,
    output_height: int,
    stream_fps: float,
    output_fps: float | None,
    segment_frames: int,
    resume_state: ResumeState,
    output_path: str,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> threading.Thread:
    encoder_thread = threading.Thread(
        target=run_encoder_worker,
        name="vp-encoder",
        kwargs={
            "encode_queue": encode_queue,
            "error_queue": error_queue,
            "stop_event": stop_event,
            "metrics": metrics,
            "ffmpeg": ffmpeg,
            "encode_config": encode_config,
            "manifest": manifest,
            "signature": signature,
            "width": output_width,
            "height": output_height,
            "fps": stream_fps,
            "output_fps": output_fps,
            "segment_frames": segment_frames,
            "resume_state": resume_state,
            "output_path": output_path,
            "encode_progress_callback": encode_progress_callback,
        },
        daemon=True,
    )

    if encode_progress_callback is not None and resume_state.completed_output_frames > 0:
        encode_progress_callback(
            resume_state.completed_output_frames,
            None,
            None,
            None,
            "continue",
        )

    encoder_thread.start()
    return encoder_thread


__all__ = ["start_raw_encoder_thread"]
