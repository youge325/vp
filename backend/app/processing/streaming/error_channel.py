"""Bounded first-error channel shared by streaming worker threads."""

from __future__ import annotations

import queue
import threading

_ERROR_QUEUE_CAPACITY = 1


def create_error_queue() -> queue.Queue[BaseException]:
    """Create the single-cause channel used by one streaming run."""
    return queue.Queue(maxsize=_ERROR_QUEUE_CAPACITY)


def report_first_error(
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    error: BaseException,
) -> bool:
    """Stop producers and retain only the first failure without blocking."""
    stop_event.set()
    try:
        error_queue.put_nowait(error)
    except queue.Full:
        return False
    return True


def take_first_error(error_queue: queue.Queue[BaseException]) -> BaseException | None:
    """Take the retained failure without a separate empty/get race."""
    try:
        return error_queue.get_nowait()
    except queue.Empty:
        return None


__all__ = ["create_error_queue", "report_first_error", "take_first_error"]
