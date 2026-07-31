"""Encoder queue worker for resumable segmented output."""

from __future__ import annotations

import queue
import threading

from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_segment_writer import EncoderSegmentWriter, EncoderWriterOwner
from app.processing.streaming.error_channel import report_first_error
from app.processing.streaming.queues import (
    EncodeQueue,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _ENCODE_END,
    _queue_get,
)


def run_encoder_worker(
    *,
    config: EncoderRuntimeConfig,
    encode_queue: EncodeQueue,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    writer_owner: EncoderWriterOwner,
) -> None:
    segment_writer = EncoderSegmentWriter(config, writer_owner)

    try:
        while not stop_event.is_set():
            item = _queue_get(encode_queue, stop_event)
            if item is None:
                continue

            if item is _ENCODE_END:
                break

            if isinstance(item, EncodedFrame):
                segment_writer.write_frame(item.frame)
                config.metrics.set_queue_depth("encode", encode_queue.qsize())
                continue

            if isinstance(item, SegmentBoundary):
                segment_writer.seal_if_ready(item.next_source_frame)
                continue

            if isinstance(item, StreamEnd):
                segment_writer.seal_remaining(item.next_source_frame)
                break
    except BaseException as exc:  # pragma: no cover - thread boundary
        report_first_error(error_queue, stop_event, exc)
    finally:
        try:
            segment_writer.discard_open_segment()
        except BaseException as exc:  # pragma: no cover - thread cleanup boundary
            report_first_error(error_queue, stop_event, exc)


__all__ = ["run_encoder_worker"]
