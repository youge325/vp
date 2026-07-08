"""Encoder worker — writes resumable video segments to disk."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.encoder_segments import (
    make_segment_progress_callback as _make_segment_progress_callback,
    resolve_segment_output_frame_count as _resolve_segment_output_frame_count,
)
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _ENCODE_END,
    _queue_get,
)
from app.utils.ffmpeg import FFmpegWrapper


def _encoder_worker(
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
    decode_queue: queue.Queue[Any],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
) -> None:
    del decode_queue, signature
    extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
    writer = None
    segment_index = len(resume_state.completed_segments) + 1
    current_segment_start = resume_state.completed_output_frames
    current_segment_input_frames = 0
    tmp_path = ""

    def seal_chunk(next_source_frame: int) -> None:
        nonlocal writer, segment_index, current_segment_start, current_segment_input_frames, tmp_path
        assert writer is not None
        writer.close()
        try:
            segment_output_frames = _resolve_segment_output_frame_count(
                ffmpeg,
                writer,
                tmp_path,
                fallback_frame_count=current_segment_input_frames,
            )
        finally:
            writer = None
        if segment_output_frames <= 0:
            # Encoder produced no frames; drop the sentinel and reset.
            Path(tmp_path).unlink(missing_ok=True)
            current_segment_input_frames = 0
            tmp_path = ""
            return
        manifest.finalize_chunk(
            tmp_path,
            index=segment_index,
            start_output_frame=current_segment_start,
            end_output_frame=current_segment_start + segment_output_frames - 1,
            next_source_frame=next_source_frame,
        )
        segment_index += 1
        current_segment_start += segment_output_frames
        current_segment_input_frames = 0
        tmp_path = ""

    try:
        while not stop_event.is_set():
            item = _queue_get(encode_queue, stop_event)
            if item is None:
                continue

            if item is _ENCODE_END:
                break

            if isinstance(item, EncodedFrame):
                if writer is None:
                    tmp_path = manifest.chunk_tmp_path(extension, index=segment_index)
                    writer = ffmpeg.open_rawvideo_encoder(
                        output_path=tmp_path,
                        width=width,
                        height=height,
                        fps=fps,
                        output_fps=output_fps,
                        encode_config=encode_config,
                        progress_callback=_make_segment_progress_callback(
                            current_segment_start,
                            encode_progress_callback,
                        ),
                    )
                writer.write_frame(item.frame)
                current_segment_input_frames += 1
                metrics.record_processed_frames(1)
                metrics.set_queue_depth("encode", encode_queue.qsize())
                continue

            if isinstance(item, SegmentBoundary):
                if writer is None:
                    continue
                if current_segment_input_frames < segment_frames:
                    continue
                seal_chunk(item.next_source_frame)
                continue

            if isinstance(item, StreamEnd):
                if writer is not None and current_segment_input_frames > 0:
                    seal_chunk(item.next_source_frame)
                break
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # pragma: no cover - cleanup best effort
                pass
        # Discard any in-flight sentinel left behind by an exception or cancel.
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - cleanup best effort
                pass
