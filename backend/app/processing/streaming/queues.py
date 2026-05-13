"""Shared queue plumbing for the streaming pipeline.

The decoder / processor / encoder workers communicate through bounded
``queue.Queue`` instances. To keep their files free of duplicate
sentinel definitions, all dataclasses, terminal sentinels, and put/get
helpers live here.

Phase D.2.2 — the previous polling interval was 100 ms, which woke each
worker ten times per second just to re-check ``stop_event``. Three
workers × 10 Hz = ~30 unnecessary wake-ups per second on the hot path.
Polling can't be removed entirely (``queue.Queue`` doesn't compose with
external ``Event``), but bumping the timeout to one second cuts the
wake-up rate by 10× while keeping the worst-case cancellation latency
inside the watchdog window managed by the Rust shell
(``VP_TASK_STALL_TIMEOUT_SECS`` defaults to 600 s).
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

# Terminal sentinels signal end-of-stream between workers. Defined once
# here so decoder/processor/encoder can all reference the same object.
_DECODE_END = object()
_ENCODE_END = object()

# Phase D.2.2 — see module docstring. Worst-case cancellation latency is
# bounded by the watchdog (default 600 s) and the FFmpeg child's own
# response to SIGTERM, so a 1 s timeout is comfortable.
_QUEUE_POLL_INTERVAL_SECONDS = 1.0


@dataclass(slots=True)
class DecodedFrame:
    """Decoded source frame packet."""

    source_index: int
    frame: np.ndarray


@dataclass(slots=True)
class EncodedFrame:
    """Processed frame ready to feed the encoder."""

    output_index: int
    frame: np.ndarray


@dataclass(slots=True)
class SegmentBoundary:
    """Natural split point after a full source-frame group."""

    next_source_frame: int


@dataclass(slots=True)
class StreamEnd:
    """Signal end-of-stream to the encoder stage."""

    next_source_frame: int


def _queue_put(target_queue: queue.Queue[Any], item: Any, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            target_queue.put(item, timeout=_QUEUE_POLL_INTERVAL_SECONDS)
            return
        except queue.Full:
            continue


def _queue_put_nowait(target_queue: queue.Queue[Any], item: Any) -> None:
    try:
        target_queue.put_nowait(item)
    except queue.Full:
        pass


def _queue_get(source_queue: queue.Queue[Any], stop_event: threading.Event) -> Any | None:
    while not stop_event.is_set():
        try:
            return source_queue.get(timeout=_QUEUE_POLL_INTERVAL_SECONDS)
        except queue.Empty:
            continue
    return None
