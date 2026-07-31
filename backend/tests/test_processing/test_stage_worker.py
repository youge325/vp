from __future__ import annotations

import io
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.cli.commands import stage_worker as stage_worker_command
from app.errors import ProcessError, TaskErrorCode
from app.generated.protocol_constants import STAGE_WORKER_EVENT_PREFIX
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.planning.processing_steps import ProcessingStep
from app.processing.streaming import stage_worker as stage_worker_runtime
from app.processing.streaming import stage_worker_progress
from app.processing.streaming.stage_worker import (
    run_stage_worker_stream,
)
from app.processing.streaming.stage_worker_config import build_stage_worker_step
from tests.support.stage_worker import (
    IdentityBackend as _IdentityBackend,
    IncrementAlgorithm as _IncrementAlgorithm,
    MidpointAlgorithm as _MidpointAlgorithm,
    ProgressSequenceAlgorithm as _ProgressSequenceAlgorithm,
    frame as _frame,
    frames_from_bytes as _frames_from_bytes,
    make_stage_worker_config as _config,
    stream_of as _stream_of,
)


class _SequenceAlgorithm:
    def process_frame_sequence(self, frames, **_kwargs):
        return [frame + 10 for frame in frames]


class _SlowSequenceAlgorithm:
    def process_frame_sequence(self, frames, **_kwargs):
        time.sleep(0.05)
        return [frame + 10 for frame in frames]


class _SlowProgressSequenceAlgorithm:
    def process_frame_sequence(self, frames, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback is not None:
            progress_callback(2, len(frames))
        time.sleep(0.05)
        return [frame + 10 for frame in frames]


def _run_worker(
    config: StageWorkerConfig,
    input_stream: io.BytesIO,
    output_stream: io.BytesIO,
    algorithm,
    event_sink,
) -> None:
    with (
        patch.object(stage_worker_runtime, "create_backend", return_value=_IdentityBackend()),
        patch.object(stage_worker_runtime, "create_algorithm", return_value=algorithm),
    ):
        run_stage_worker_stream(
            config,
            input_stream,
            output_stream,
            event_sink=lambda event: event_sink(event.model_dump(by_alias=True, exclude_none=True, mode="json")),
            model_root="D:/models",
        )


def _run_sequence_algorithm(algorithm) -> tuple[io.BytesIO, list[dict]]:
    output = io.BytesIO()
    events: list[dict] = []
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=3,
    )
    _run_worker(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        algorithm,
        events.append,
    )
    return output, events


def test_single_frame_stage_reads_and_writes_rawvideo_frames() -> None:
    output = io.BytesIO()
    events = []
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "placeholder", "scale_factor": 1.0},
            stage_name="01_super_resolution",
        ),
        input_frame_count=2,
    )

    _run_worker(
        config,
        _stream_of([_frame(1), _frame(2)]),
        output,
        _IncrementAlgorithm(),
        events.append,
    )

    frames = _frames_from_bytes(output.getvalue(), count=2)
    assert [int(frame[0, 0, 0]) for frame in frames] == [2, 3]
    assert events[-1]["type"] == "progress"
    assert events[-1]["current"] == 2


def test_interpolation_stage_outputs_source_and_intermediate_frames() -> None:
    output = io.BytesIO()
    events = []
    config = _config(
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="01_frame_interpolation",
        ),
        input_frame_count=2,
    )

    _run_worker(
        config,
        _stream_of([_frame(0), _frame(90)]),
        output,
        _MidpointAlgorithm(),
        events.append,
    )

    frames = _frames_from_bytes(output.getvalue(), count=4)
    assert [int(frame[0, 0, 0]) for frame in frames] == [0, 30, 60, 90]
    assert events[-1]["current"] == events[-1]["total"] == 1


def test_sequence_stage_buffers_all_input_frames_before_writing_output() -> None:
    output, _events = _run_sequence_algorithm(_SequenceAlgorithm())

    frames = _frames_from_bytes(output.getvalue(), count=3)
    assert [int(frame[0, 0, 0]) for frame in frames] == [11, 12, 13]


def test_sequence_stage_emits_start_and_heartbeat_during_blocking_process(monkeypatch) -> None:
    monkeypatch.setattr(stage_worker_progress, "SEQUENCE_STAGE_HEARTBEAT_SECONDS", 0.01)
    _output, events = _run_sequence_algorithm(_SlowSequenceAlgorithm())

    progress_events = [event for event in events if event["type"] == "progress"]
    assert progress_events[0] == {
        "type": "progress",
        "stageName": "01_super_resolution",
        "stageIndex": 1,
        "stageTotal": 1,
        "current": 0,
        "total": 3,
        "heartbeat": False,
        "force": True,
    }
    assert any(event.get("heartbeat") is True and event["current"] == 0 for event in progress_events)
    assert progress_events[-1]["current"] == 3


def test_sequence_stage_heartbeat_uses_latest_algorithm_progress(monkeypatch) -> None:
    monkeypatch.setattr(stage_worker_progress, "SEQUENCE_STAGE_HEARTBEAT_SECONDS", 0.01)
    _output, events = _run_sequence_algorithm(_SlowProgressSequenceAlgorithm())

    heartbeat_events = [event for event in events if event.get("heartbeat") is True]
    assert heartbeat_events
    assert all(event["current"] == 2 for event in heartbeat_events)
    assert all(event["total"] == 3 for event in heartbeat_events)


def test_sequence_stage_skips_write_progress_when_algorithm_reports_progress() -> None:
    _output, events = _run_sequence_algorithm(_ProgressSequenceAlgorithm())

    progress_events = [event for event in events if event["type"] == "progress"]
    assert [event["current"] for event in progress_events] == [0, 3, 3]
    assert not any(event["current"] in (1, 2) for event in progress_events)


def test_stage_worker_passes_configured_backend_to_algorithm() -> None:
    output = io.BytesIO()
    captured = {}

    def fake_create(stage, backend, *, model_root):
        captured["stage"] = stage
        captured["backend"] = backend
        captured["model_root"] = model_root
        return _SequenceAlgorithm()

    config = StageWorkerConfig(
        stage=build_stage_worker_step(
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={
                    "sr_algorithm": "ppmsvsr",
                    "scale_factor": 4.0,
                    "tensor_backend": "paddle",
                    "onnx_model": None,
                    "engine": "cuda",
                    "num_frames": 5,
                },
                stage_name="01_super_resolution",
            )
        ),
        stage_index=1,
        stage_total=1,
        stage_name="01_super_resolution",
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        input_frame_count=1,
        tensor_backend_name="paddle",
        output_frame_count=1,
    )

    backend = _IdentityBackend()
    with (
        patch.object(stage_worker_runtime, "create_backend", return_value=backend) as create_backend_mock,
        patch.object(stage_worker_runtime, "create_algorithm", side_effect=fake_create),
    ):
        run_stage_worker_stream(
            config,
            _stream_of([_frame(1)]),
            output,
            event_sink=lambda _event: None,
            model_root="D:/models",
        )

    create_backend_mock.assert_called_once()
    assert captured["stage"].stage_name == config.stage_name
    assert captured["backend"] is backend
    assert captured["model_root"] == "D:/models"


def test_stage_worker_error_event_uses_wire_error_code(monkeypatch, capsys) -> None:
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=1,
    )

    monkeypatch.setattr(
        stage_worker_command,
        "load_stage_worker_config",
        lambda _path: config,
    )

    def fail_stream(*_args, **_kwargs):
        raise ProcessError(TaskErrorCode.MISSING_MODEL, "missing aux weight", details={"path": "spynet.pdparams"})

    monkeypatch.setattr(stage_worker_command, "run_stage_worker_stream", fail_stream)

    with pytest.raises(SystemExit):
        stage_worker_command.cmd_stage_worker(SimpleNamespace(config_json="unused.json"))

    stderr = capsys.readouterr().err
    line = next(line for line in stderr.splitlines() if line.startswith(STAGE_WORKER_EVENT_PREFIX))
    event = json.loads(line[len(STAGE_WORKER_EVENT_PREFIX) :])
    assert event["type"] == "error"
    assert event["code"] == TaskErrorCode.MISSING_MODEL.value
    assert event["message"] == "missing aux weight"


def test_stage_worker_event_write_failure_never_contaminates_rawvideo_stdout(monkeypatch, capsys) -> None:
    monkeypatch.setattr(stage_worker_command, "load_stage_worker_config", lambda _path: object())

    def fail_stream(*_args, **_kwargs):
        raise RuntimeError("worker failed")

    monkeypatch.setattr(stage_worker_command, "run_stage_worker_stream", fail_stream)
    monkeypatch.setattr(
        stage_worker_command,
        "emit_stage_event",
        lambda _event: (_ for _ in ()).throw(OSError("stderr closed")),
    )

    with pytest.raises(SystemExit) as exc_info:
        stage_worker_command.cmd_stage_worker(SimpleNamespace(config_json="unused.json"))

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.out == ""
    assert captured.err == ""
