"""Queue IO helpers for in-process processor streams."""

from __future__ import annotations

import queue
import threading
from typing import Iterator

from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _DECODE_END,
    _ENCODE_END,
    _queue_get,
    _queue_put,
)


def emit_encoded_payload(
    *,
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    output_index: int,
    payload: FramePayload,
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    frame = payload.ensure_numpy(metrics)
    _queue_put(
        encode_queue,
        EncodedFrame(output_index=output_index, frame=frame),
        stop_event,
    )
    metrics.set_queue_depth("encode", encode_queue.qsize())


def drain_decoded(
    decode_queue: queue.Queue[DecodedFrame | object],
    stop_event: threading.Event,
) -> Iterator[DecodedFrame]:
    """Yield ``DecodedFrame`` items until stop_event fires or ``_DECODE_END`` is seen."""
    while not stop_event.is_set():
        item = _queue_get(decode_queue, stop_event)
        if item is None:
            continue
        if item is _DECODE_END:
            return
        if isinstance(item, DecodedFrame):
            yield item


def emit_stream_end(
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    source_frames: int,
    stop_event: threading.Event,
) -> None:
    """Tail of every processor stream: StreamEnd marker + encoder sentinel."""
    _queue_put(encode_queue, StreamEnd(next_source_frame=source_frames), stop_event)
    _queue_put(encode_queue, _ENCODE_END, stop_event)


__all__ = [
    "drain_decoded",
    "emit_encoded_payload",
    "emit_stream_end",
]
