from __future__ import annotations

import queue
import threading

from app.processing.streaming.queues import StreamEnd, _ENCODE_END
from app.processing.streaming.worker_pipeline_queue import (
    enqueue_worker_pipeline_abort,
    enqueue_worker_pipeline_stream_end,
)


def test_enqueue_worker_pipeline_stream_end_uses_source_frame_count() -> None:
    encode_queue: queue.Queue = queue.Queue()

    enqueue_worker_pipeline_stream_end(
        encode_queue=encode_queue,
        stop_event=threading.Event(),
        source_frames=7,
    )

    item = encode_queue.get_nowait()
    assert isinstance(item, StreamEnd)
    assert item.next_source_frame == 7


def test_enqueue_worker_pipeline_abort_uses_encoder_terminal_sentinel() -> None:
    encode_queue: queue.Queue = queue.Queue()

    enqueue_worker_pipeline_abort(encode_queue=encode_queue)

    assert encode_queue.get_nowait() is _ENCODE_END
