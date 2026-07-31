from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
import app.processing.streaming.stage_file_chunk_runtime as runtime
from app.processing.streaming.stage_file_chunk_runtime import run_stage_chunk_to_file
from app.processing.streaming.worker_plans import StageChunkPlan
from tests.support.raw_video import (
    FakeRawVideoMedia,
    frame as _frame,
    make_stage_file_runtime_config,
)


def _run_chunk(
    *,
    ffmpeg: Any,
    output_path: Path,
    step: ProcessingStep,
    chunk: StageChunkPlan,
    progress_callback: Any = None,
) -> int:
    config = make_stage_file_runtime_config(
        ffmpeg,
        PipelineMetrics(),
        step=step,
        progress_callback=progress_callback,
    )
    return run_stage_chunk_to_file(
        config=config,
        output_path=str(output_path),
        chunk=chunk,
        stage_total_frames=10,
    )


def test_stage_chunk_runtime_writes_unskipped_worker_frames(monkeypatch, tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": 4.0,
            "sr_algorithm": "ppmsvsr",
            "onnx_model": None,
            "engine": "cuda",
            "num_frames": 10,
        },
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
        group = SimpleNamespace(
            handles=[SimpleNamespace(process=fake_process, plan=plans[0])],
            start_decoded_frame_writer=lambda config, **_kwargs: decoded_configs.append(config),
        )
        yield group

    decoded_configs = []

    monkeypatch.setattr(runtime, "stage_worker_session", fake_session)

    ffmpeg = FakeRawVideoMedia(payload=b"encoded")
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
        algorithm_kwargs={
            "scale_factor": 1.0,
            "sr_algorithm": "placeholder",
            "onnx_model": None,
            "engine": "cuda",
            "num_frames": 10,
        },
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
        yield SimpleNamespace(
            handles=[SimpleNamespace(process=process, plan=plans[0])],
            start_decoded_frame_writer=lambda *_args, **_kwargs: None,
        )

    expected = RuntimeError("encode failed")

    def fail_encode(**_kwargs: Any) -> int:
        raise expected

    monkeypatch.setattr(runtime, "stage_worker_session", fake_session)
    monkeypatch.setattr(runtime, "encode_stage_worker_output", fail_encode)

    with pytest.raises(RuntimeError, match="encode failed") as exc_info:
        _run_chunk(ffmpeg=object(), output_path=tmp_path / "chunk.mp4", step=step, chunk=chunk)

    assert exc_info.value is expected
    assert captured["stop_event"].is_set()
    assert captured["error_queue"].empty()
