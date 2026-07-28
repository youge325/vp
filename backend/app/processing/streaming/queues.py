"""Shared encode-queue plumbing for the streaming pipeline.

Stage-worker runtimes push processed frame packets into bounded
``queue.Queue`` instances. The encoder worker consumes the same
dataclasses and terminal sentinel, while queue helpers centralize
stop-event polling.

Polling remains necessary because ``queue.Queue`` does not compose with an
external ``Event``. A one-second timeout bounds wake-up overhead and keeps the
worst-case cancellation latency inside the watchdog window managed by the Rust shell
(``VP_TASK_STALL_TIMEOUT_SECS`` defaults to 600 s).
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

import numpy as np

# See module docstring. Worst-case cancellation latency is
# bounded by the watchdog (default 600 s) and the FFmpeg child's own
# response to SIGTERM, so a 1 s timeout is comfortable.
_QUEUE_POLL_INTERVAL_SECONDS = 1.0


@dataclass(slots=True)
class EncodedFrame:
    """Processed frame ready to feed the encoder."""

    frame: np.ndarray


@dataclass(slots=True)
class SegmentBoundary:
    """Natural split point after a full source-frame group."""

    next_source_frame: int


@dataclass(slots=True)
class StreamEnd:
    """Signal end-of-stream to the encoder stage."""

    next_source_frame: int


class _EncodeEnd:
    __slots__ = ()


_ENCODE_END = _EncodeEnd()
type EncodeQueueItem = EncodedFrame | SegmentBoundary | StreamEnd | _EncodeEnd
type EncodeQueue = queue.Queue[EncodeQueueItem]


def _queue_put(target_queue: EncodeQueue, item: EncodeQueueItem, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            target_queue.put(item, timeout=_QUEUE_POLL_INTERVAL_SECONDS)
            return
        except queue.Full:
            continue


def _queue_put_nowait(target_queue: EncodeQueue, item: EncodeQueueItem) -> None:
    try:
        target_queue.put_nowait(item)
    except queue.Full:
        pass


def _queue_get(source_queue: EncodeQueue, stop_event: threading.Event) -> EncodeQueueItem | None:
    while not stop_event.is_set():
        try:
            return source_queue.get(timeout=_QUEUE_POLL_INTERVAL_SECONDS)
        except queue.Empty:
            continue
    return None
