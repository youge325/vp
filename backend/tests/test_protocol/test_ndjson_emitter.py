"""Concurrency guarantees for the shared NDJSON stdout emitter."""

from __future__ import annotations

import json
import sys
import threading
import time
from typing import Any

from app.generated.contracts import VideoInfo
from app.generated.protocol_constants import BackendEnvelopeType
from app.protocol import _NdjsonEmitter


class _OverlapDetectingStream:
    def __init__(self) -> None:
        self._state_lock = threading.Lock()
        self._active_writers = 0
        self.overlapped = False
        self.fragments: list[str] = []

    def write(self, value: str) -> int:
        with self._state_lock:
            self._active_writers += 1
            self.overlapped = self.overlapped or self._active_writers > 1
        time.sleep(0.002)
        self.fragments.append(value)
        with self._state_lock:
            self._active_writers -= 1
        return len(value)

    def flush(self) -> None:
        time.sleep(0.001)


def test_concurrent_emits_are_complete_non_overlapping_lines(monkeypatch: Any) -> None:
    stream = _OverlapDetectingStream()
    monkeypatch.setattr(sys, "stdout", stream)
    emitter = _NdjsonEmitter()
    worker_count = 12
    start = threading.Barrier(worker_count)

    def emit(index: int) -> None:
        start.wait()
        emitter.emit(
            BackendEnvelopeType.INFO,
            VideoInfo(fps=24.0, width=index, height=1080, videoCodec=f"h264-{index}"),
        )

    workers = [threading.Thread(target=emit, args=(index,)) for index in range(worker_count)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=2)

    assert all(not worker.is_alive() for worker in workers)
    assert stream.overlapped is False
    lines = "".join(stream.fragments).splitlines()
    payloads = [json.loads(line) for line in lines]
    assert len(payloads) == worker_count
    assert {payload["width"] for payload in payloads} == set(range(worker_count))
