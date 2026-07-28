"""Lightweight metrics container for the streaming pipeline.

职责:
1. 给队列水位 / 实测 fps / tensor transfer 提供线程安全的存储,
   避免每个 caller 自己 hack 一个 dict + Lock。
2. 让 NDJSON ``progress`` 帧能可选地携带这些字段(向后兼容,前端忽略未知字段)。
3. 不依赖外部库(无 prometheus_client / no psutil),避免给 backend
   再引入新 dependency。

当前 rawvideo 路径由 stage-worker 子进程、主进程 encoder queue 和
``encoder_worker`` 共同更新 metrics；stage-file 路径复用同一个容器来
记录 chunk encoding 与 tensor transfer 统计。

Usage::

    metrics = PipelineMetrics()
    metrics.set_queue_depth("decoded", queue.qsize())
    metrics.record_processed_frames(1)
    snapshot = metrics.snapshot()
    # snapshot 形如:
    # {
    #     "queueDepths": {"decoded": 12, "encoded": 3},
    #     "stageDurationsSeconds": {},
    #     "processedFrames": 100,
    #     "measuredFps": 23.5,
    #     "elapsedSeconds": 4.25,
    # }
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _MetricsState:
    """Mutable inner state — only accessed under ``PipelineMetrics._lock``."""

    queue_depths: dict[str, int] = field(default_factory=dict)
    transfer_counts: dict[str, int] = field(default_factory=lambda: {"h2d": 0, "d2h": 0})
    transfer_durations: dict[str, float] = field(default_factory=lambda: {"h2d": 0.0, "d2h": 0.0})
    processed_frames: int = 0
    started_at: float = field(default_factory=time.time)


class PipelineMetrics:
    """Thread-safe metrics container for the streaming pipeline.

    Designed for the current stage-worker and encoder-thread runtimes.
    All public methods acquire a single ``threading.Lock``; granularity
    isn't fine but contention is low because updates happen at stage,
    queue, and frame boundaries.
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

    # ------- host/device transfers -------

    def record_transfer(self, kind: str, count: int = 1, *, seconds: float = 0.0) -> None:
        """Increment a host/device transfer counter.

        ``kind`` is intentionally tiny and stable: ``h2d`` for host-to-device
        uploads and ``d2h`` for device-to-host downloads.
        """
        if kind not in {"h2d", "d2h"}:
            raise ValueError(f"Unknown transfer kind: {kind!r}")
        with self._lock:
            self._state.transfer_counts[kind] = self._state.transfer_counts.get(kind, 0) + max(int(count), 0)
            self._state.transfer_durations[kind] = self._state.transfer_durations.get(kind, 0.0) + max(
                float(seconds),
                0.0,
            )

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
                "stageDurationsSeconds": {},
                "transferCounts": dict(self._state.transfer_counts),
                "transferDurationsSeconds": {
                    name: round(value, 6) for name, value in self._state.transfer_durations.items()
                },
                "processedFrames": processed,
                "measuredFps": round(measured_fps, 2) if measured_fps is not None else None,
                "elapsedSeconds": round(elapsed, 3),
            }


__all__ = ["PipelineMetrics"]
