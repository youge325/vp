from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from app.planning.manifest import ResumeState
from tests.support.streaming_runtime import create_test_manifest
from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_encoder import start_raw_encoder_thread
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd


def _minimal_encoder_config(tmp_path: Path) -> EncoderRuntimeConfig:
    output_path = str(tmp_path / "out.mp4")
    return EncoderRuntimeConfig(
        ffmpeg=object(),  # type: ignore[arg-type]
        encode_config={},
        manifest=create_test_manifest(output_path),
        width=1,
        height=1,
        fps=24.0,
        output_fps=None,
        segment_frames=1,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        output_path=output_path,
        encode_progress_callback=None,
        metrics=PipelineMetrics(),
    )


def test_start_raw_encoder_thread_wires_worker_and_resume_progress(tmp_path: Path, monkeypatch) -> None:
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    worker_calls: list[dict[str, Any]] = []
    progress_events: list[tuple[int, str]] = []
    config = EncoderRuntimeConfig(
        ffmpeg=object(),  # type: ignore[arg-type]
        encode_config={"container": "mp4"},
        manifest=manifest,
        width=2,
        height=3,
        fps=24.0,
        output_fps=None,
        segment_frames=10,
        resume_state=ResumeState(start_source_frame=5, completed_output_frames=7, completed_segments=[]),
        output_path=str(tmp_path / "out.mp4"),
        encode_progress_callback=lambda frame, _fps, _speed, _time, progress: progress_events.append((frame, progress)),
        metrics=PipelineMetrics(),
    )

    def fake_run_encoder_worker(**kwargs: Any) -> None:
        worker_calls.append(kwargs)

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_raw_encoder.run_encoder_worker",
        fake_run_encoder_worker,
    )

    owner = start_raw_encoder_thread(
        config=config,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
    )

    assert owner.finish(deadline=time.monotonic() + 1) is True

    assert not any(thread.name == "vp-encoder" for thread in threading.enumerate())
    assert progress_events == [(7, "continue")]
    assert worker_calls
    worker_kwargs = worker_calls[0]
    assert worker_kwargs["encode_queue"] is encode_queue
    assert worker_kwargs["error_queue"] is error_queue
    assert worker_kwargs["stop_event"] is stop_event
    assert worker_kwargs["config"] is config
    assert worker_kwargs["writer_owner"] is not None
    assert config.width == 2
    assert config.height == 3
    assert config.fps == 24.0


def test_raw_encoder_owner_terminates_stuck_writer_before_bounded_join(tmp_path: Path, monkeypatch) -> None:
    import time

    from app.processing.streaming import pipeline_raw_encoder as module

    writer_attached = threading.Event()
    writer_released = threading.Event()
    lifecycle: list[str] = []

    class BlockingWriter:
        output_frame_count = 0

        def write_frame(self, _frame) -> None:
            writer_released.wait(timeout=1)

        def close(self) -> None:
            lifecycle.append("close")

        def terminate_and_reap(self, *, deadline: float) -> bool:
            assert deadline >= time.monotonic()
            lifecycle.append("terminate-reap")
            writer_released.set()
            return True

    def stuck_worker(*, writer_owner, **_kwargs: Any) -> None:
        writer = BlockingWriter()
        assert writer_owner.attach(writer) is True
        writer_attached.set()
        try:
            writer.write_frame(None)
        finally:
            writer_owner.detach(writer)

    monkeypatch.setattr(module, "run_encoder_worker", stuck_worker)
    config = _minimal_encoder_config(tmp_path)
    owner = start_raw_encoder_thread(
        config=config,
        encode_queue=queue.Queue(),
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )
    assert writer_attached.wait(timeout=1)

    assert owner.abort(deadline=time.monotonic() + 1) is True

    assert not any(thread.name == "vp-encoder" for thread in threading.enumerate())
    assert lifecycle == ["terminate-reap"]


def test_raw_encoder_owner_rejects_unbounded_deadline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.processing.streaming.pipeline_raw_encoder.run_encoder_worker", lambda **_kwargs: None)
    owner = start_raw_encoder_thread(
        config=_minimal_encoder_config(tmp_path),
        encode_queue=queue.Queue(),
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )

    with pytest.raises(ValueError, match="finite"):
        owner.finish(deadline=float("inf"))


def test_raw_encoder_owner_is_retained_until_late_process_reap(tmp_path: Path, monkeypatch) -> None:
    from app.processing.streaming import pipeline_raw_encoder as module

    writer_attached = threading.Event()
    allow_cleanup = threading.Event()
    release_worker = threading.Event()

    class DelayedWriter:
        output_frame_count = 0

        def terminate_and_reap(self, *, deadline: float) -> bool:
            assert deadline >= 0
            if not allow_cleanup.is_set():
                return False
            release_worker.set()
            return True

        def write_frame(self, _frame) -> None:
            release_worker.wait(timeout=2)

        def close(self) -> None:
            pass

    def delayed_worker(*, writer_owner, **_kwargs: Any) -> None:
        writer = DelayedWriter()
        assert writer_owner.attach(writer)
        writer_attached.set()
        try:
            writer.write_frame(None)
        finally:
            writer_owner.detach(writer)

    monkeypatch.setattr(module, "run_encoder_worker", delayed_worker)
    owner = start_raw_encoder_thread(
        config=_minimal_encoder_config(tmp_path),
        encode_queue=queue.Queue(),
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )
    assert writer_attached.wait(timeout=1)

    assert owner.abort(deadline=time.monotonic() + 0.01) is False
    try:
        assert any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
    finally:
        allow_cleanup.set()
        for thread in tuple(threading.enumerate()):
            if thread.name.startswith("vp-late-cleanup-"):
                thread.join(timeout=1)

    assert not any(thread.name in {"vp-encoder"} for thread in threading.enumerate())
    assert not any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
