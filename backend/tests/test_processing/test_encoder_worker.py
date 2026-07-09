from __future__ import annotations

import queue
import threading
from typing import Any

from app.processing.streaming.queues import StreamEnd


def test_run_encoder_worker_seals_stream_end_and_discards_open_segment(monkeypatch) -> None:
    from app.processing.streaming import encoder_worker as module

    instances: list[Any] = []

    class FakeSegmentWriter:
        def __init__(self, **_kwargs: Any) -> None:
            self.actions: list[tuple[str, int] | tuple[str]] = []
            instances.append(self)

        def write_frame(self, _frame: bytes) -> None:
            self.actions.append(("write",))

        def seal_if_ready(self, next_source_frame: int) -> None:
            self.actions.append(("seal_if_ready", next_source_frame))

        def seal_remaining(self, next_source_frame: int) -> None:
            self.actions.append(("seal_remaining", next_source_frame))

        def discard_open_segment(self) -> None:
            self.actions.append(("discard",))

    monkeypatch.setattr(module, "EncoderSegmentWriter", FakeSegmentWriter)
    encode_queue: queue.Queue[Any] = queue.Queue()
    encode_queue.put(StreamEnd(next_source_frame=7))

    module.run_encoder_worker(
        ffmpeg=object(),
        encode_config={},
        manifest=object(),
        signature="sig",
        width=128,
        height=72,
        fps=24.0,
        output_fps=None,
        segment_frames=1000,
        resume_state=object(),
        output_path="out.mp4",
        encode_queue=encode_queue,
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
        encode_progress_callback=None,
        metrics=object(),
    )

    assert instances
    assert instances[0].actions == [("seal_remaining", 7), ("discard",)]
