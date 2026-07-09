"""Encoder queue worker for resumable segmented output."""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.encoder_segment_writer import EncoderSegmentWriter
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd, _ENCODE_END, _queue_get
from app.utils.ffmpeg import FFmpegWrapper


def run_encoder_worker(
    *,
    ffmpeg: FFmpegWrapper,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    width: int,
    height: int,
    fps: float,
    output_fps: float | None,
    segment_frames: int,
    resume_state: ResumeState,
    output_path: str,
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
) -> None:
    del signature
    segment_writer = EncoderSegmentWriter(
        ffmpeg=ffmpeg,
        encode_config=encode_config,
        manifest=manifest,
        width=width,
        height=height,
        fps=fps,
        output_fps=output_fps,
        segment_frames=segment_frames,
        resume_state=resume_state,
        output_path=output_path,
        encode_progress_callback=encode_progress_callback,
        metrics=metrics,
    )

    try:
        while not stop_event.is_set():
            item = _queue_get(encode_queue, stop_event)
            if item is None:
                continue

            if item is _ENCODE_END:
                break

            if isinstance(item, EncodedFrame):
                segment_writer.write_frame(item.frame)
                metrics.set_queue_depth("encode", encode_queue.qsize())
                continue

            if isinstance(item, SegmentBoundary):
                segment_writer.seal_if_ready(item.next_source_frame)
                continue

            if isinstance(item, StreamEnd):
                segment_writer.seal_remaining(item.next_source_frame)
                break
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
    finally:
        segment_writer.discard_open_segment()


__all__ = ["run_encoder_worker"]
