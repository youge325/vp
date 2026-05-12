"""Lightweight metrics container for the streaming pipeline.

Phase C.1.3 引入。三个进程内目标:
1. 给将来想接入的"队列水位 / 实测 fps / 每阶段耗时"提供线程安全的存储,
   避免每个 caller 自己 hack 一个 dict + Lock。
2. 让 NDJSON ``progress`` 帧能可选地携带这些字段(向后兼容,前端忽略未知字段)。
3. 不依赖外部库(无 prometheus_client / no psutil),避免给 backend
   再引入新 dependency。

本次只提供数据结构与同步原语,具体接入到 ``_run_streaming_pipeline``
留给后续 PR 演进 — Pipeline 接入是大改且需要回归测试覆盖。

Usage::

    metrics = PipelineMetrics()
    with metrics.timed("decode"):
        ...
    metrics.set_queue_depth("decoded", queue.qsize())
    metrics.record_processed_frames(1)
    snapshot = metrics.snapshot()
    # snapshot 形如:
    # {
    #     "queueDepths": {"decoded": 12, "encoded": 3},
    #     "stageDurationsSeconds": {"decode": 0.42, "process": 1.05},
    #     "processedFrames": 100,
    #     "measuredFps": 23.5,
    #     "elapsedSeconds": 4.25,
    # }
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class _MetricsState:
    """Mutable inner state — only accessed under ``PipelineMetrics._lock``."""

    queue_depths: dict[str, int] = field(default_factory=dict)
    stage_durations: dict[str, float] = field(default_factory=dict)
    processed_frames: int = 0
    started_at: float = field(default_factory=time.time)


class PipelineMetrics:
    """Thread-safe metrics container for the streaming pipeline.

    Designed for the three-worker producer/consumer model in
    ``processing/streaming/pipeline.py``. All public methods acquire a
    single ``threading.Lock``; granularity isn't fine but contention is
    low (decode / process / encode threads emit at most a few hundred
    metrics updates per second on the hot path).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = _MetricsState()

    # ------- queue depth -------

    def set_queue_depth(self, name: str, depth: int) -> None:
        """Record the current depth of a named queue.

        Called by the producer/consumer threads each time they ``put`` or
        ``get`` so the snapshot reflects the latest known water mark.
        """
        with self._lock:
            self._state.queue_depths[name] = max(int(depth), 0)

    # ------- stage timing -------

    @contextmanager
    def timed(self, stage: str) -> Iterator[None]:
        """Context manager that records elapsed seconds under ``stage``."""
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            with self._lock:
                # accumulate so multiple invocations of the same stage add up
                self._state.stage_durations[stage] = self._state.stage_durations.get(stage, 0.0) + elapsed

    def record_stage_duration(self, stage: str, seconds: float) -> None:
        """Same as ``timed`` but for callers that already measured externally."""
        with self._lock:
            self._state.stage_durations[stage] = self._state.stage_durations.get(stage, 0.0) + max(float(seconds), 0.0)

    # ------- frame throughput -------

    def record_processed_frames(self, count: int = 1) -> None:
        """Increment the processed-frame counter."""
        with self._lock:
            self._state.processed_frames += max(int(count), 0)

    # ------- snapshot -------

    def snapshot(self) -> dict[str, Any]:
        """Read-only snapshot for serialising into the NDJSON progress frame.

        Returns plain python primitives; safe to ``json.dumps`` directly.
        ``measuredFps`` is derived from ``processed_frames / elapsed`` and
        clamped to ``None`` if no frame has been processed yet (avoids a
        division-by-zero / misleading 0 fps).
        """
        with self._lock:
            elapsed = max(time.time() - self._state.started_at, 1e-6)
            processed = self._state.processed_frames
            measured_fps = (processed / elapsed) if processed > 0 else None
            return {
                "queueDepths": dict(self._state.queue_depths),
                "stageDurationsSeconds": {name: round(value, 4) for name, value in self._state.stage_durations.items()},
                "processedFrames": processed,
                "measuredFps": round(measured_fps, 2) if measured_fps is not None else None,
                "elapsedSeconds": round(elapsed, 3),
            }


__all__ = ["PipelineMetrics"]
