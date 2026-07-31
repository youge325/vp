"""Shared late-cleanup coordinator for process-backed owners."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from app.generated.protocol_constants import TERMINATION_REAP_TIMEOUT_MS


class _LateCleanupOwner(Protocol):
    def retry_cleanup(self, *, deadline: float) -> bool: ...


@dataclass(frozen=True, slots=True)
class _LateCleanupEntry:
    thread: threading.Thread
    deadline: float


class _LateCleanupCoordinator:
    """Retain failed owners for one bounded, daemon-backed cleanup window."""

    def __init__(
        self,
        *,
        timeout_seconds: float = TERMINATION_REAP_TIMEOUT_MS / 1000,
        retry_interval_seconds: float = 0.01,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Late cleanup timeout must be positive.")
        if retry_interval_seconds <= 0:
            raise ValueError("Late cleanup retry interval must be positive.")
        self._timeout_seconds = timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._lock = threading.Lock()
        self._entries: dict[int, _LateCleanupEntry] = {}
        self._closed = False

    def submit(self, owner: _LateCleanupOwner) -> None:
        owner_id = id(owner)
        deadline = time.monotonic() + self._timeout_seconds
        with self._lock:
            if self._closed:
                raise RuntimeError("Late cleanup coordinator is closed.")
            if owner_id in self._entries:
                return
            thread = threading.Thread(
                target=self._run,
                name=f"vp-late-cleanup-{owner_id}",
                args=(owner_id, owner, deadline),
                daemon=True,
            )
            self._entries[owner_id] = _LateCleanupEntry(thread, deadline)
        try:
            thread.start()
        except BaseException:
            with self._lock:
                self._entries.pop(owner_id, None)
            raise

    def close(self) -> None:
        """Stop accepting owners and wait only through each entry's original deadline."""
        with self._lock:
            self._closed = True
            entries = tuple(self._entries.values())
        for entry in entries:
            scheduling_grace = 0.05
            entry.thread.join(timeout=max(entry.deadline + scheduling_grace - time.monotonic(), 0.0))
        alive = [entry.thread.name for entry in entries if entry.thread.is_alive()]
        if alive:
            logging.getLogger(__name__).error(
                "Late cleanup owners exceeded the termination deadline: %s",
                ", ".join(alive),
            )

    def _run(self, owner_id: int, owner: _LateCleanupOwner, deadline: float) -> None:
        try:
            while time.monotonic() < deadline:
                try:
                    cleanup_finished = owner.retry_cleanup(deadline=deadline)
                except BaseException:  # pragma: no cover - last-resort ownership boundary
                    logging.getLogger(__name__).exception("Late process cleanup attempt failed")
                    cleanup_finished = False
                if cleanup_finished:
                    return
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(self._retry_interval_seconds, remaining))
            logging.getLogger(__name__).error(
                "Late process cleanup exceeded the %.3fs termination deadline",
                self._timeout_seconds,
            )
        finally:
            with self._lock:
                self._entries.pop(owner_id, None)


late_cleanup_coordinator = _LateCleanupCoordinator()


__all__ = ["late_cleanup_coordinator"]
