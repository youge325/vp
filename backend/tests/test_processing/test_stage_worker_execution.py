from __future__ import annotations

import io

import numpy as np
import pytest

from app.planning import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.stage_worker_execution import (
    run_interpolation_stage,
    run_sequence_stage,
    run_single_frame_stage,
)
from app.processing.streaming.stage_worker_io import RawVideoFrameError


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
    def process_frame_pair(self, frame0, frame1, *, timestep: float = 0.5):
        prev = frame0["tensor"].astype(np.float32)
        cur = frame1["tensor"].astype(np.float32)
        return {"tensor": np.rint(prev + (cur - prev) * timestep).astype(np.uint8)}


class _ProgressSequenceAlgorithm:
    def process_frame_sequence(self, frames, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback is not None:
            progress_callback(len(frames), len(frames))
        return [frame + 10 for frame in frames]


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _stream_of(frames: list[np.ndarray]) -> io.BytesIO:
    return io.BytesIO(b"".join(np.ascontiguousarray(frame).tobytes() for frame in frames))


def _frames_from_bytes(raw: bytes, *, count: int) -> list[np.ndarray]:
    assert len(raw) == count * 3
    return [
        np.frombuffer(raw[index * 3 : (index + 1) * 3], dtype=np.uint8).reshape((1, 1, 3)) for index in range(count)
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


def test_single_frame_execution_reads_processes_and_writes_frames() -> None:
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

    written = run_single_frame_stage(
        config,
        _stream_of([_frame(1), _frame(2)]),
        output,
        _IdentityBackend(),
        _IncrementAlgorithm(),
        events.append,
        PipelineMetrics(),
    )

    frames = _frames_from_bytes(output.getvalue(), count=2)
    assert written == 2
    assert [int(frame[0, 0, 0]) for frame in frames] == [2, 3]
    assert events[-1]["current"] == 2


def test_interpolation_execution_outputs_source_and_mid_frames() -> None:
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

    written = run_interpolation_stage(
        config,
        _stream_of([_frame(0), _frame(90)]),
        output,
        _IdentityBackend(),
        _MidpointAlgorithm(),
        events.append,
        PipelineMetrics(),
    )

    frames = _frames_from_bytes(output.getvalue(), count=4)
    assert written == 4
    assert [int(frame[0, 0, 0]) for frame in frames] == [0, 30, 60, 90]
    assert events[-1]["current"] == events[-1]["total"] == 1


def test_sequence_execution_uses_algorithm_progress_instead_of_write_progress() -> None:
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

    written = run_sequence_stage(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        _ProgressSequenceAlgorithm(),
        events.append,
    )

    frames = _frames_from_bytes(output.getvalue(), count=3)
    progress_events = [event for event in events if event["type"] == "progress"]
    assert written == 3
    assert [int(frame[0, 0, 0]) for frame in frames] == [11, 12, 13]
    assert [event["current"] for event in progress_events] == [0, 3, 3]


def test_sequence_execution_rejects_streams_shorter_than_configured_count() -> None:
    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=2,
    )

    with pytest.raises(RawVideoFrameError, match="declared input frames"):
        run_sequence_stage(
            config,
            _stream_of([_frame(1)]),
            io.BytesIO(),
            _ProgressSequenceAlgorithm(),
            lambda _event: None,
        )
