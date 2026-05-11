"""Decoder worker — pulls raw frames from ffmpeg into the decode queue."""

from __future__ import annotations

import queue
import threading
from typing import Any

from app.processing.streaming.queues import (
    DecodedFrame,
    _DECODE_END,
    _queue_put,
    _queue_put_nowait,
)
from app.utils.ffmpeg import FFmpegWrapper


def _decoder_worker(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    width: int,
    height: int,
    start_source_frame: int,
    source_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    del encode_queue
    try:
        if start_source_frame >= source_frames:
            _queue_put(decode_queue, _DECODE_END, stop_event)
            return

        reader = ffmpeg.open_rawvideo_decoder(
            input_path=input_path,
            width=width,
            height=height,
            decode_config=decode_config,
            start_frame=start_source_frame,
        )
        try:
            source_index = start_source_frame
            while not stop_event.is_set():
                frame = reader.read_frame()
                if frame is None:
                    break
                _queue_put(decode_queue, DecodedFrame(source_index=source_index, frame=frame), stop_event)
                source_index += 1
        finally:
            reader.close()

        _queue_put(decode_queue, _DECODE_END, stop_event)
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        _queue_put_nowait(decode_queue, _DECODE_END)
