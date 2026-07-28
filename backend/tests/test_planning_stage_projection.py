from __future__ import annotations

from app.planning import ProcessingStep, StageProjection, build_stage_plan


def test_stage_projection_owns_order_frame_counts_and_fps() -> None:
    steps = (
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder"},
            stage_name="01_super_resolution",
        ),
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="02_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="frame_filter_chain",
            algorithm_kwargs={"filters": ()},
            stage_name="03_postprocess",
        ),
    )

    projection = StageProjection(steps)
    stages = projection.stages(source_frames=4, source_fps=24.0)

    assert [stage.step.stage_name for stage in stages] == [
        "01_super_resolution",
        "02_frame_interpolation",
        "03_postprocess",
    ]
    assert [(stage.input_frames, stage.output_frames) for stage in stages] == [
        (4, 4),
        (4, 10),
        (10, 10),
    ]
    assert [(stage.input_fps, stage.output_fps) for stage in stages] == [
        (24.0, 24.0),
        (24.0, 72.0),
        (72.0, 72.0),
    ]


def test_stage_plan_uses_stage_projection_as_its_step_source() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2},
        stage_name="01_frame_interpolation",
    )

    projection = StageProjection((step,))
    plan = build_stage_plan(projection, 5, source_duration=1.0, output_fps=None)

    assert plan.projection is projection
    assert plan.steps is plan.projection.steps
    assert plan.processed_output_frames == plan.projection.output_frame_count(5)
    assert plan.projection.output_fps(24.0) == 48.0
