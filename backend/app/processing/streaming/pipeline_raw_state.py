"""Raw pipeline queue and stop-event state."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd

_RawEncodeQueueItem = EncodedFrame | SegmentBoundary | StreamEnd | object


@dataclass(frozen=True)
class RawPipelineState:
    encode_queue: queue.Queue[_RawEncodeQueueItem]
    error_queue: queue.Queue[BaseException]
    stop_event: threading.Event


def create_raw_pipeline_state(*, encode_queue_size: int = 8) -> RawPipelineState:
    return RawPipelineState(
        encode_queue=queue.Queue(maxsize=encode_queue_size),
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )


__all__ = ["RawPipelineState", "create_raw_pipeline_state"]
