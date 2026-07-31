from __future__ import annotations

import io

import pytest

from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_execution import (
    run_interpolation_stage,
    run_sequence_stage,
    run_single_frame_stage,
)
from app.processing.streaming.stage_worker_config import processing_step_from_config
from app.processing.streaming.stage_worker_io import RawVideoFrameError
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


def _collect(events):
    return lambda event: events.append(event.model_dump(by_alias=True, exclude_none=True, mode="json"))


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

    run_single_frame_stage(
        config,
        processing_step_from_config(config),
        _stream_of([_frame(1), _frame(2)]),
        output,
        _IdentityBackend(),
        _IncrementAlgorithm(),
        _collect(events),
        PipelineMetrics(),
    )

    frames = _frames_from_bytes(output.getvalue(), count=2)
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

    run_interpolation_stage(
        config,
        processing_step_from_config(config),
        _stream_of([_frame(0), _frame(90)]),
        output,
        _IdentityBackend(),
        _MidpointAlgorithm(),
        _collect(events),
        PipelineMetrics(),
    )

    frames = _frames_from_bytes(output.getvalue(), count=4)
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

    run_sequence_stage(
        config,
        _stream_of([_frame(1), _frame(2), _frame(3)]),
        output,
        _ProgressSequenceAlgorithm(),
        _collect(events),
    )

    frames = _frames_from_bytes(output.getvalue(), count=3)
    progress_events = [event for event in events if event["type"] == "progress"]
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


def test_sequence_execution_rejects_algorithm_output_count_mismatch() -> None:
    class ExtraFrameAlgorithm:
        def process_frame_sequence(self, frames, *, progress_callback: object = None):
            del progress_callback
            return [*frames, _frame(9)]

    config = _config(
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        input_frame_count=2,
    )

    with pytest.raises(RawVideoFrameError, match="expected 2, got 3"):
        run_sequence_stage(
            config,
            _stream_of([_frame(1), _frame(2)]),
            io.BytesIO(),
            ExtraFrameAlgorithm(),
            lambda _event: None,
        )
