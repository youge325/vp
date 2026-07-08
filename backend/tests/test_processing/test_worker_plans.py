from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.worker_plans import (
    boundary_schedule_for_stage_plan,
    build_stage_chunk_plans,
    build_stage_worker_plans,
)


def test_worker_plans_track_dimensions_frames_and_stage_backends() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 2.0,
                "sr_algorithm": "placeholder",
                "onnx_model": "sr.onnx",
                "tensor_backend": "paddle",
            },
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

    assert [plan.config.stage_name for plan in plans] == ["01_frame_interpolation", "02_super_resolution"]
    assert [plan.config.input_frame_count for plan in plans] == [3, 7]
    assert [plan.output_frame_count for plan in plans] == [7, 7]
    assert plans[1].config.input_width == 2
    assert plans[1].config.output_width == 4
    assert plans[1].config.tensor_backend_name == "paddle"


def test_interpolation_chunk_plans_use_lookahead_and_skip_duplicate_boundaries() -> None:
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


def test_boundary_schedule_maps_output_counts_to_next_source_frame() -> None:
    stage_plan = build_stage_plan(
        [
            ProcessingStep(
                algorithm_type="frame_interpolation",
                algorithm_kwargs={"multi": 2},
                stage_name="01_frame_interpolation",
            )
        ],
        4,
        source_duration=1.0,
        output_fps=None,
    )

    assert boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=1,
        source_frames=4,
    ) == {2: 2, 4: 3}
