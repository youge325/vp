from __future__ import annotations

import pytest

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from tests.support.video_metadata import make_video_metadata


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
    stages = projection.stages(make_video_metadata(4, duration=4 / 24))

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
    assert [stage.output_fps for stage in stages] == [24.0, 72.0, 72.0]


def test_stage_plan_materializes_projection_as_its_only_stage_source() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2},
        stage_name="01_frame_interpolation",
    )

    projection = StageProjection((step,))
    plan = build_stage_plan(projection, make_video_metadata(5, duration=1.0), output_fps=None)

    assert plan.processing_steps == projection.steps
    assert plan.stream_fps == 48.0
    assert plan.stages[0].input_frames == 5


@pytest.mark.parametrize(
    "section",
    [
        {"enabled": True, "filters": []},
        {
            "enabled": True,
            "filters": [{"kind": "sharpen", "enabled": False, "params": {}}],
        },
    ],
)
def test_projection_omits_filter_stages_without_enabled_work(section: dict[str, object]) -> None:
    workflow = {
        "preprocess": section,
        "postprocess": {"enabled": False, "filters": []},
        "interpolation": {"enabled": False},
        "superResolution": {"enabled": False},
        "processOrder": "super_resolution_then_interpolation",
    }

    assert StageProjection.from_workflow(workflow).steps == ()


def test_projection_applies_filter_geometry_and_super_resolution_in_execution_order() -> None:
    projection = StageProjection(
        (
            ProcessingStep(
                algorithm_type="frame_filter_chain",
                algorithm_kwargs={
                    "filters": (
                        {"kind": "scale", "enabled": True, "params": {"mode": "factor", "factor": 0.5}},
                        {"kind": "crop", "enabled": True, "params": {"x": 5, "y": 3, "width": 70, "height": 40}},
                        {
                            "kind": "pad",
                            "enabled": True,
                            "params": {"top": 2, "bottom": 4, "left": 6, "right": 8},
                        },
                    )
                },
                stage_name="01_preprocess",
            ),
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={"scale_factor": 4, "sr_algorithm": "edvr"},
                stage_name="02_super_resolution",
            ),
        )
    )

    stages = projection.stages(make_video_metadata(3, duration=3 / 24))

    assert [(stage.input_width, stage.input_height, stage.output_width, stage.output_height) for stage in stages] == [
        (320, 180, 84, 46),
        (84, 46, 336, 184),
    ]


@pytest.mark.parametrize(
    "filter_step",
    [
        {"kind": "scale", "enabled": True, "params": {"mode": "factor", "factor": -1}},
        {"kind": "scale", "enabled": True, "params": {"mode": "resolution", "width": 0, "height": 10}},
        {"kind": "crop", "enabled": True, "params": {"x": -1, "y": 0, "width": 4, "height": 4}},
        {"kind": "pad", "enabled": True, "params": {"left": -1}},
    ],
)
def test_projection_rejects_geometry_that_execution_cannot_apply(filter_step: dict[str, object]) -> None:
    projection = StageProjection(
        (
            ProcessingStep(
                algorithm_type="frame_filter_chain",
                algorithm_kwargs={"filters": (filter_step,)},
                stage_name="01_preprocess",
            ),
        )
    )

    with pytest.raises(ValueError):
        projection.stages(make_video_metadata(1, duration=1 / 24, width=16, height=12))
