from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_encoder import start_raw_encoder_thread
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd


def test_start_raw_encoder_thread_wires_worker_and_resume_progress(tmp_path: Path, monkeypatch) -> None:
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    worker_calls: list[dict[str, Any]] = []
    progress_events: list[tuple[int, str]] = []

    def fake_run_encoder_worker(**kwargs: Any) -> None:
        worker_calls.append(kwargs)

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_raw_encoder.run_encoder_worker",
        fake_run_encoder_worker,
    )

    thread = start_raw_encoder_thread(
        ffmpeg=object(),  # type: ignore[arg-type]
        encode_config={"container": "mp4"},
        manifest=manifest,
        output_width=2,
        output_height=3,
        stream_fps=24.0,
        output_fps=None,
        segment_frames=10,
        resume_state=ResumeState(start_source_frame=5, completed_output_frames=7, completed_segments=[]),
        output_path=str(tmp_path / "out.mp4"),
        encode_progress_callback=lambda frame, _fps, _speed, _time, progress: progress_events.append((frame, progress)),
        metrics=PipelineMetrics(),
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
    )

    thread.join(timeout=1)

    assert thread.is_alive() is False
    assert progress_events == [(7, "continue")]
    assert worker_calls
    worker_kwargs = worker_calls[0]
    assert worker_kwargs["encode_queue"] is encode_queue
    assert worker_kwargs["error_queue"] is error_queue
    assert worker_kwargs["stop_event"] is stop_event
    assert worker_kwargs["width"] == 2
    assert worker_kwargs["height"] == 3
    assert worker_kwargs["fps"] == 24.0
