from __future__ import annotations

import io
import json
import time
from types import SimpleNamespace

import numpy as np
import pytest

from app.algorithms.factory import AlgorithmFactory
from app.cli.commands import stage_worker as stage_worker_command
from app.errors import ProcessError, TaskErrorCode
from app.planning import ProcessingStep
from app.processing.streaming import stage_worker_progress
from app.processing.streaming.stage_worker import (
    run_stage_worker_stream,
)
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.stage_worker_progress import STAGE_EVENT_PREFIX


class _IdentityBackend:
    def numpy_to_tensor(self, frame):
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor):
        return tensor["tensor"].copy()

    def get_name(self) -> str:
        return "identity"


class _IncrementAlgorithm:
    def process_frame(self, tensor):
        return {"tensor": tensor["tensor"] + 1}


class _MidpointAlgorithm:
    def needs_frame_pairs(self) -> bool:
        return True

    def process_frame_pair(self, frame0, frame1, *, timestep: float = 0.5):
        prev = frame0["tensor"].astype(np.float32)
        cur = frame1["tensor"].astype(np.float32)
        return {"tensor": np.rint(prev + (cur - prev) * timestep).astype(np.uint8)}


class _SequenceAlgorithm:
    def needs_frame_sequence(self) -> bool:
        return True

    def process_frame_sequence(self, frames, **_kwargs):
        return [frame + 10 for frame in frames]


class _SlowSequenceAlgorithm:
    def needs_frame_sequence(self) -> bool:
        return True

    def process_frame_sequence(self, frames, **_kwargs):
        time.sleep(0.05)
        return [frame + 10 for frame in frames]


class _ProgressSequenceAlgorithm:
    def needs_frame_sequence(self) -> bool:
        return True

    def process_frame_sequence(self, frames, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback is not None:
            progress_callback(len(frames), len(frames))
        return [frame + 10 for frame in frames]


class _SlowProgressSequenceAlgorithm:
    def needs_frame_sequence(self) -> bool:
        return True

    def process_frame_sequence(self, frames, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback is not None:
            progress_callback(2, len(frames))
        time.sleep(0.05)
        return [frame + 10 for frame in frames]


def _frame(value: int, *, height: int = 1, width: int = 1) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def _stream_of(frames: list[np.ndarray]) -> io.BytesIO:
    return io.BytesIO(b"".join(np.ascontiguousarray(frame).tobytes() for frame in frames))


def _frames_from_bytes(raw: bytes, *, count: int, height: int = 1, width: int = 1) -> list[np.ndarray]:
    frame_bytes = height * width * 3
    assert len(raw) == count * frame_bytes
    return [
        np.frombuffer(raw[index * frame_bytes : (index + 1) * frame_bytes], dtype=np.uint8).reshape((height, width, 3))
        for index in range(count)
    ]


def _config(step: ProcessingStep, *, input_frame_count: int = 2) -> StageWorkerConfig:
    return StageWorkerConfig(
        stage=step,
        stage_index=1,
        stage_total=1,
        stage_name=step.stage_name,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        input_frame_count=input_frame_count,
        tensor_backend_name="identity",
    )


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

    run_stage_worker_stream(
        config,
        _stream_of([_frame(1), _frame(2)]),
        output,
        algorithm_factory=lambda _stage, _backend: _IncrementAlgorithm(),
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=events.append,
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

    run_stage_worker_stream(
        config,
        _stream_of([_frame(0), _frame(90)]),
        output,
        algorithm_factory=lambda _stage, _backend: _MidpointAlgorithm(),
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=events.append,
    )

    frames = _frames_from_bytes(output.getvalue(), count=4)
    assert [int(frame[0, 0, 0]) for frame in frames] == [0, 30, 60, 90]
    assert events[-1]["current"] == events[-1]["total"] == 1


def test_sequence_stage_buffers_all_input_frames_before_writing_output() -> None:
    output = io.BytesIO()
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=3,
    )

    run_stage_worker_stream(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        algorithm_factory=lambda _stage, _backend: _SequenceAlgorithm(),
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=lambda _event: None,
    )

    frames = _frames_from_bytes(output.getvalue(), count=3)
    assert [int(frame[0, 0, 0]) for frame in frames] == [11, 12, 13]


def test_sequence_stage_emits_start_and_heartbeat_during_blocking_process(monkeypatch) -> None:
    output = io.BytesIO()
    events = []
    monkeypatch.setattr(stage_worker_progress, "SEQUENCE_STAGE_HEARTBEAT_SECONDS", 0.01)
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=3,
    )

    run_stage_worker_stream(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        algorithm_factory=lambda _stage, _backend: _SlowSequenceAlgorithm(),
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=events.append,
    )

    progress_events = [event for event in events if event["type"] == "progress"]
    assert progress_events[0] == {
        "type": "progress",
        "stageName": "01_super_resolution",
        "stageIndex": 1,
        "stageTotal": 1,
        "current": 0,
        "total": 3,
        "force": True,
    }
    assert any(event.get("heartbeat") is True and event["current"] == 0 for event in progress_events)
    assert progress_events[-1]["current"] == 3


def test_sequence_stage_heartbeat_uses_latest_algorithm_progress(monkeypatch) -> None:
    output = io.BytesIO()
    events = []
    monkeypatch.setattr(stage_worker_progress, "SEQUENCE_STAGE_HEARTBEAT_SECONDS", 0.01)
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=3,
    )

    run_stage_worker_stream(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        algorithm_factory=lambda _stage, _backend: _SlowProgressSequenceAlgorithm(),
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=events.append,
    )

    heartbeat_events = [event for event in events if event.get("heartbeat") is True]
    assert heartbeat_events
    assert all(event["current"] == 2 for event in heartbeat_events)
    assert all(event["total"] == 3 for event in heartbeat_events)


def test_sequence_stage_skips_write_progress_when_algorithm_reports_progress() -> None:
    output = io.BytesIO()
    events = []
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=3,
    )

    run_stage_worker_stream(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        algorithm_factory=lambda _stage, _backend: _ProgressSequenceAlgorithm(),
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=events.append,
    )

    progress_events = [event for event in events if event["type"] == "progress"]
    assert [event["current"] for event in progress_events] == [0, 3, 3]
    assert not any(event["current"] in (1, 2) for event in progress_events)


def test_stage_worker_uses_stage_tensor_backend_without_passing_it_to_algorithm(monkeypatch) -> None:
    output = io.BytesIO()
    captured = {}

    def fake_create(*, algorithm_type, tensor_backend, tensor_backend_name, **kwargs):
        captured["algorithm_type"] = algorithm_type
        captured["tensor_backend"] = tensor_backend
        captured["tensor_backend_name"] = tensor_backend_name
        captured["kwargs"] = kwargs
        return _SequenceAlgorithm()

    monkeypatch.setattr(AlgorithmFactory, "create", staticmethod(fake_create))
    config = StageWorkerConfig(
        stage=ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr", "tensor_backend": "paddle", "num_frames": 5},
            stage_name="01_super_resolution",
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
    )

    run_stage_worker_stream(
        config,
        _stream_of([_frame(1)]),
        output,
        backend_factory=lambda _name: _IdentityBackend(),
        event_sink=lambda _event: None,
    )

    assert captured["algorithm_type"] == "super_resolution"
    assert captured["tensor_backend"].get_name() == "identity"
    assert captured["tensor_backend_name"] == "identity"
    assert captured["kwargs"] == {"sr_algorithm": "ppmsvsr", "num_frames": 5}


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
        stage_worker_command.StageWorkerConfig,
        "from_json_file",
        classmethod(lambda _cls, _path: config),
    )

    def fail_stream(*_args, **_kwargs):
        raise ProcessError(TaskErrorCode.MISSING_MODEL, "missing aux weight", details={"path": "spynet.pdparams"})

    monkeypatch.setattr(stage_worker_command, "run_stage_worker_stream", fail_stream)

    with pytest.raises(SystemExit):
        stage_worker_command.cmd_stage_worker(SimpleNamespace(config_json="unused.json"))

    stderr = capsys.readouterr().err
    line = next(line for line in stderr.splitlines() if line.startswith(STAGE_EVENT_PREFIX))
    event = json.loads(line[len(STAGE_EVENT_PREFIX) :])
    assert event["type"] == "error"
    assert event["code"] == TaskErrorCode.MISSING_MODEL.value
    assert event["message"] == "missing aux weight"
