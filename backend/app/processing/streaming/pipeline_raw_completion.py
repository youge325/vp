"""Raw pipeline completion and result aggregation."""

from __future__ import annotations

import queue
import threading

from app.planning import SegmentManifest


def finish_raw_pipeline_runtime(
    *,
    encoder_thread: threading.Thread,
    error_queue: queue.Queue[BaseException],
    manifest: SegmentManifest,
) -> int:
    encoder_thread.join()

    if not error_queue.empty():
        raise error_queue.get()

    completed_segments = manifest.scan_completed_chunks()
    return sum(segment.frame_count for segment in completed_segments)


__all__ = ["finish_raw_pipeline_runtime"]
