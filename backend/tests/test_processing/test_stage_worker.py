from __future__ import annotations

import io

import numpy as np
import pytest

from app.planning import ProcessingStep
from app.processing.streaming.stage_worker import (
    RawVideoFrameError,
    StageWorkerConfig,
    read_rgb_frame,
    run_stage_worker_stream,
)


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

    def process_frame_sequence(self, frames):
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


def test_stage_worker_config_accepts_jsonable_stage_shape() -> None:
    config = StageWorkerConfig.from_mapping(
        {
            "stage": {
                "algorithm_type": "super_resolution",
                "algorithm_kwargs": {"scale_factor": 2.0},
                "stage_name": "01_super_resolution",
            },
            "stageIndex": 1,
            "stageTotal": 2,
            "stageName": "01_super_resolution",
            "inputWidth": 320,
            "inputHeight": 180,
            "outputWidth": 640,
            "outputHeight": 360,
            "inputFrameCount": 12,
            "tensorBackendName": "onnx",
        }
    )

    assert config.stage.algorithm_type == "super_resolution"
    assert config.stage.algorithm_kwargs == {"scale_factor": 2.0}
    assert config.output_width == 640
    assert config.tensor_backend_name == "onnx"


def test_read_rgb_frame_rejects_partial_frame() -> None:
    with pytest.raises(RawVideoFrameError, match="partial rawvideo frame"):
        read_rgb_frame(io.BytesIO(b"\x00\x01"), width=1, height=1)


def test_single_frame_stage_reads_and_writes_rawvideo_frames() -> None:
    output = io.BytesIO()
    events = []
    config = _config(
        ProcessingStep(
            algorithm_type="anime_optimization",
            algorithm_kwargs={},
            stage_name="01_anime_optimization",
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
        event_sink=lambda _event: None,
    )

    frames = _frames_from_bytes(output.getvalue(), count=4)
    assert [int(frame[0, 0, 0]) for frame in frames] == [0, 30, 60, 90]


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
