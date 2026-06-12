"""Unit tests for ``app.processing.streaming.metrics``.

Phase C.1.3 — verify queue-depth tracking, timed-stage accumulation, and
the ``snapshot()`` output shape consumed by the NDJSON progress frame.
"""

from __future__ import annotations

import threading
import time

from app.processing.streaming.metrics import PipelineMetrics


def test_snapshot_empty_pipeline_has_no_fps() -> None:
    metrics = PipelineMetrics()
    snapshot = metrics.snapshot()
    assert snapshot["processedFrames"] == 0
    assert snapshot["measuredFps"] is None
    assert snapshot["queueDepths"] == {}
    assert snapshot["stageDurationsSeconds"] == {}
    assert snapshot["transferCounts"] == {"h2d": 0, "d2h": 0}
    assert snapshot["elapsedSeconds"] >= 0.0


def test_record_transfer_counts_host_device_edges() -> None:
    metrics = PipelineMetrics()
    metrics.record_transfer("h2d")
    metrics.record_transfer("h2d", 2)
    metrics.record_transfer("d2h")

    snapshot = metrics.snapshot()

    assert snapshot["transferCounts"] == {"h2d": 3, "d2h": 1}


def test_set_queue_depth_clamps_negative_to_zero() -> None:
    metrics = PipelineMetrics()
    metrics.set_queue_depth("decoded", 12)
    metrics.set_queue_depth("encoded", -5)
    snapshot = metrics.snapshot()
    assert snapshot["queueDepths"] == {"decoded": 12, "encoded": 0}


def test_timed_context_accumulates_across_invocations() -> None:
    metrics = PipelineMetrics()
    with metrics.timed("decode"):
        time.sleep(0.01)
    with metrics.timed("decode"):
        time.sleep(0.01)
    snapshot = metrics.snapshot()
    decode_duration = snapshot["stageDurationsSeconds"]["decode"]
    # Two ~10 ms sleeps should sum to >= 20 ms; allow some slack for slow CI
    assert decode_duration >= 0.015, f"decode duration {decode_duration} < 0.015"


def test_record_stage_duration_adds_directly() -> None:
    metrics = PipelineMetrics()
    metrics.record_stage_duration("process", 0.5)
    metrics.record_stage_duration("process", 0.25)
    snapshot = metrics.snapshot()
    assert snapshot["stageDurationsSeconds"]["process"] == 0.75


def test_record_processed_frames_increments_fps() -> None:
    metrics = PipelineMetrics()
    metrics.record_processed_frames(10)
    metrics.record_processed_frames(20)
    snapshot = metrics.snapshot()
    assert snapshot["processedFrames"] == 30
    # measured fps depends on wall clock, but with 30 frames in < 1s it must be > 0
    assert snapshot["measuredFps"] is not None
    assert snapshot["measuredFps"] > 0


def test_metrics_are_thread_safe() -> None:
    """Concurrent updates from many threads must not corrupt the counters."""
    metrics = PipelineMetrics()
    threads_count = 10
    increments_per_thread = 100

    def worker() -> None:
        for _ in range(increments_per_thread):
            metrics.record_processed_frames(1)
            metrics.set_queue_depth("decoded", 1)

    threads = [threading.Thread(target=worker) for _ in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snapshot = metrics.snapshot()
    assert snapshot["processedFrames"] == threads_count * increments_per_thread
    assert snapshot["queueDepths"]["decoded"] == 1
