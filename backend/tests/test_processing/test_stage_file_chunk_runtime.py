from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from app.planning import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
import app.processing.streaming.stage_file_chunk_runtime as runtime
from app.processing.streaming.stage_file_chunk_runtime import run_stage_chunk_to_file
from app.processing.streaming.worker_plans import StageChunkPlan


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


class _FakeWriter:
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self.frames: list[np.ndarray] = []
        self.output_frame_count = 0
        self.closed = False

    def write_frame(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def close(self) -> None:
        self.closed = True
        self.output_frame_count = len(self.frames)
        Path(self.output_path).write_bytes(b"encoded")


class _FakeFFmpeg:
    def __init__(self) -> None:
        self.writer: _FakeWriter | None = None

    def open_rawvideo_encoder(self, *, output_path: str, **kwargs: Any) -> _FakeWriter:
        del kwargs
        self.writer = _FakeWriter(output_path)
        return self.writer

    def get_frame_count(self, _path: str) -> int:
        return 0


def _run_chunk(
    *,
    ffmpeg: Any,
    output_path: Path,
    step: ProcessingStep,
    chunk: StageChunkPlan,
    progress_callback: Any = None,
) -> int:
    return run_stage_chunk_to_file(
        ffmpeg=ffmpeg,
        input_path="input.mp4",
        decode_config={},
        encode_config={"container": "mp4"},
        output_path=str(output_path),
        step=step,
        stage_index=1,
        stage_total=1,
        tensor_backend_name="paddle",
        progress_callback=progress_callback,
        chunk=chunk,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        stage_total_frames=10,
        output_fps=24.0,
        encode_output_fps=None,
        metrics=PipelineMetrics(),
    )


def test_stage_chunk_runtime_writes_unskipped_worker_frames(monkeypatch, tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    chunk = StageChunkPlan(
        input_start_frame=2,
        input_frame_count=3,
        logical_input_frame_count=3,
        raw_output_frame_count=3,
        written_output_frame_count=2,
        skip_output_frames=1,
    )
    stdout = BytesIO(b"".join(np.ascontiguousarray(_frame(value)).tobytes() for value in (1, 2, 3)))
    fake_process = SimpleNamespace(stdin=BytesIO(), stdout=stdout)
    progress_events = []

    @contextmanager
    def fake_session(plans, *, progress_callbacks, **_kwargs):
        progress_callbacks[0](3, 999, phase="stage")
        yield [SimpleNamespace(process=fake_process, plan=plans[0])]

    decoded_configs = []

    @contextmanager
    def fake_decoded_frame_writer_session(config, **_kwargs):
        decoded_configs.append(config)
        yield

    monkeypatch.setattr(runtime, "stage_worker_session", fake_session)
    monkeypatch.setattr(runtime, "decoded_frame_writer_session", fake_decoded_frame_writer_session)

    ffmpeg = _FakeFFmpeg()
    output_path = tmp_path / "chunk.mp4"

    encoded_frames = _run_chunk(
        ffmpeg=ffmpeg,
        output_path=output_path,
        step=step,
        progress_callback=lambda current, total, **kwargs: progress_events.append((current, total, kwargs)),
        chunk=chunk,
    )

    assert encoded_frames == 2
    assert output_path.read_bytes() == b"encoded"
    assert progress_events == [(5, 10, {"phase": "stage"})]
    assert [(config.width, config.height) for config in decoded_configs] == [(1, 1)]
    assert ffmpeg.writer is not None
    assert ffmpeg.writer.closed is True
    assert [int(frame[0, 0, 0]) for frame in ffmpeg.writer.frames] == [2, 3]


def test_stage_chunk_runtime_preserves_direct_error_without_requeue(monkeypatch, tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    chunk = StageChunkPlan(
        input_start_frame=0,
        input_frame_count=1,
        logical_input_frame_count=1,
        raw_output_frame_count=1,
        written_output_frame_count=1,
        skip_output_frames=0,
    )
    process = SimpleNamespace(stdin=BytesIO(), stdout=BytesIO())
    captured = {}

    @contextmanager
    def fake_session(plans, *, error_queue, stop_event, **_kwargs):
        captured["error_queue"] = error_queue
        captured["stop_event"] = stop_event
        yield [SimpleNamespace(process=process, plan=plans[0])]

    @contextmanager
    def fake_decoded_frame_writer_session(_config, **_kwargs):
        yield

    expected = RuntimeError("encode failed")

    def fail_encode(**_kwargs: Any) -> int:
        raise expected

    monkeypatch.setattr(runtime, "stage_worker_session", fake_session)
    monkeypatch.setattr(runtime, "decoded_frame_writer_session", fake_decoded_frame_writer_session)
    monkeypatch.setattr(runtime, "encode_stage_worker_output", fail_encode)

    with pytest.raises(RuntimeError, match="encode failed") as exc_info:
        _run_chunk(ffmpeg=object(), output_path=tmp_path / "chunk.mp4", step=step, chunk=chunk)

    assert exc_info.value is expected
    assert captured["stop_event"].is_set()
    assert captured["error_queue"].empty()
