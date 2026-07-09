"""Encode-queue terminal signals for the stage-worker pipeline."""

from __future__ import annotations

import queue
import threading
from typing import Any

from app.processing.streaming.queues import StreamEnd, _ENCODE_END, _queue_put, _queue_put_nowait


def enqueue_worker_pipeline_stream_end(
    *,
    encode_queue: queue.Queue[Any],
    stop_event: threading.Event,
    source_frames: int,
) -> None:
    _queue_put(encode_queue, StreamEnd(next_source_frame=int(source_frames)), stop_event)


def enqueue_worker_pipeline_abort(*, encode_queue: queue.Queue[Any]) -> None:
    _queue_put_nowait(encode_queue, _ENCODE_END)


__all__ = ["enqueue_worker_pipeline_abort", "enqueue_worker_pipeline_stream_end"]
