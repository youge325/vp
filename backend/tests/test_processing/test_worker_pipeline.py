from __future__ import annotations

import app.processing.streaming.pipeline as streaming_pipeline
from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.stage_rules import (
    ordered_steps,
    stage_output_dimensions,
    stage_output_frame_count,
    stage_tensor_backend_name,
)
from app.processing.streaming.worker_plans import (
    boundary_schedule_for_stage_plan,
    build_stage_chunk_plans,
    build_stage_worker_plans,
)


def test_worker_plan_tracks_dimensions_for_super_resolution_then_interpolation() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder", "onnx_model": "sr.onnx"},
            stage_name="01_super_resolution",
        ),
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="02_frame_interpolation",
        ),
    ]
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        source_width=2,
        source_height=3,
        source_frame_count=3,
    )

    assert [plan.output_frame_count for plan in plans] == [3, 5]
    assert plans[0].config.input_width == 2
    assert plans[0].config.input_height == 3
    assert plans[0].config.output_width == 4
    assert plans[0].config.output_height == 6
    assert plans[1].config.input_width == 4
    assert plans[1].config.input_height == 6
    assert plans[1].config.output_width == 4
    assert plans[1].config.output_height == 6
    assert plans[1].config.input_frame_count == 3


def test_stage_rules_centralize_stage_order_dimensions_and_backend_selection() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 4.0,
                "sr_algorithm": "ppmsvsr",
                "tensor_backend": "paddle",
            },
            stage_name="01_super_resolution",
        ),
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="02_frame_interpolation",
        ),
    ]
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)

    assert [step.stage_name for step in ordered_steps(stage_plan)] == [
        "01_super_resolution",
        "02_frame_interpolation",
    ]
    assert stage_tensor_backend_name(steps[0], "onnx") == "paddle"
    assert stage_output_dimensions(steps[0], input_width=2, input_height=3) == (8, 12)
    assert stage_output_frame_count(steps[1], 3) == 7


def test_worker_plan_tracks_frame_counts_for_interpolation_then_super_resolution() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder", "onnx_model": "sr.onnx"},
            stage_name="02_super_resolution",
        ),
    ]
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        source_width=2,
        source_height=3,
        source_frame_count=3,
    )

    assert [plan.config.input_frame_count for plan in plans] == [3, 7]
    assert [plan.output_frame_count for plan in plans] == [7, 7]
    assert [plan.config.output_frame_count for plan in plans] == [7, 7]
    assert plans[0].config.output_width == 2
    assert plans[0].config.output_height == 3
    assert plans[1].config.input_width == 2
    assert plans[1].config.input_height == 3
    assert plans[1].config.output_width == 4
    assert plans[1].config.output_height == 6


def test_interpolation_stage_chunks_use_lookahead_and_skip_duplicate_boundary() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2},
        stage_name="01_frame_interpolation",
    )

    chunks = build_stage_chunk_plans(step, input_frame_count=5, segment_frames=2)

    assert [
        (
            chunk.input_start_frame,
            chunk.input_frame_count,
            chunk.logical_input_frame_count,
            chunk.raw_output_frame_count,
            chunk.skip_output_frames,
            chunk.written_output_frame_count,
        )
        for chunk in chunks
    ] == [
        (0, 3, 2, 5, 0, 5),
        (2, 3, 2, 5, 1, 4),
        (4, 1, 1, 1, 1, 0),
    ]
    assert sum(chunk.written_output_frame_count for chunk in chunks) == 9


def test_super_resolution_stage_chunks_keep_input_frame_counts_bounded() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="02_super_resolution",
    )

    chunks = build_stage_chunk_plans(step, input_frame_count=5, segment_frames=2)

    assert [
        (chunk.input_start_frame, chunk.input_frame_count, chunk.written_output_frame_count) for chunk in chunks
    ] == [
        (0, 2, 2),
        (2, 2, 2),
        (4, 1, 1),
    ]
    assert max(chunk.input_frame_count for chunk in chunks) == 2
    assert sum(chunk.written_output_frame_count for chunk in chunks) == 5


def test_stage_file_resume_source_frames_use_final_stage_input_domain() -> None:
    stage_plan = build_stage_plan(
        [
            ProcessingStep(
                algorithm_type="frame_interpolation",
                algorithm_kwargs={"multi": 2},
                stage_name="01_frame_interpolation",
            ),
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
                stage_name="02_super_resolution",
            ),
        ],
        5,
        source_duration=5 / 24,
        output_fps=None,
    )

    assert streaming_pipeline._stage_file_resume_source_frames(stage_plan, 5) == 9


def test_boundary_schedule_matches_interpolation_output_groups() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="01_frame_interpolation",
        )
    ]
    stage_plan = build_stage_plan(steps, 4, source_duration=1.0, output_fps=None)

    schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=1,
        source_frames=4,
    )

    assert schedule == {2: 2, 4: 3}


def test_boundary_schedule_matches_single_frame_output_groups() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0},
            stage_name="01_super_resolution",
        )
    ]
    stage_plan = build_stage_plan(steps, 4, source_duration=1.0, output_fps=None)

    schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=1,
        source_frames=4,
    )

    assert schedule == {1: 2, 2: 3}
