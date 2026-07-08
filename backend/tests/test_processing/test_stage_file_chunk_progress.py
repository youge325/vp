from __future__ import annotations

from app.planning import ProcessingStep
from app.processing.streaming.stage_file_chunk_progress import (
    chunk_progress_adapter,
    stage_chunk_output_start,
)
from app.processing.streaming.worker_plans import StageChunkPlan


def test_chunk_progress_adapter_offsets_interpolation_by_source_frame() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 3},
        stage_name="01_frame_interpolation",
    )
    chunk = StageChunkPlan(
        input_start_frame=2,
        input_frame_count=3,
        logical_input_frame_count=2,
        raw_output_frame_count=7,
        written_output_frame_count=6,
        skip_output_frames=1,
    )
    calls = []
    adapter = chunk_progress_adapter(
        step,
        chunk=chunk,
        total=10,
        callback=lambda current, total, **kwargs: calls.append((current, total, kwargs)),
    )

    adapter(3, 999, phase="stage")

    assert stage_chunk_output_start(step, chunk) == 6
    assert calls == [(5, 10, {"phase": "stage"})]


def test_chunk_progress_adapter_offsets_non_interpolation_by_output_frame() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    chunk = StageChunkPlan(
        input_start_frame=4,
        input_frame_count=2,
        logical_input_frame_count=2,
        raw_output_frame_count=2,
        written_output_frame_count=2,
    )
    calls = []
    adapter = chunk_progress_adapter(
        step,
        chunk=chunk,
        total=10,
        callback=lambda current, total, **kwargs: calls.append((current, total, kwargs)),
    )

    adapter(3, 999, phase="stage")

    assert stage_chunk_output_start(step, chunk) == 4
    assert calls == [(7, 10, {"phase": "stage"})]
