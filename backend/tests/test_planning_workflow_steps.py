"""Planning-layer workflow-to-stage helpers."""

from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from tests.support.video_metadata import make_video_metadata
from app.planning.workflow_steps import resolve_primary_algorithm
from tests.support.workflow_configs import make_workflow_config as _workflow


def test_workflow_step_planning_uses_canonical_order():
    projection = StageProjection.from_workflow(_workflow(superResolution={"enabled": True, "algorithm": "placeholder"}))
    assert [step.algorithm_type for step in projection.steps] == [
        "super_resolution",
        "frame_interpolation",
    ]
    assert resolve_primary_algorithm(_workflow()) == "frame_interpolation"


def test_stage_projection_builds_ordered_stage_names_and_kwargs():
    projection = StageProjection.from_workflow(
        _workflow(
            superResolution={
                "enabled": True,
                "scaleFactor": 4.0,
                "algorithm": "ppmsvsr",
                "tensorBackend": "paddle",
                "engine": "cuda",
                "numFrames": 8,
            },
            preprocess={"enabled": True, "filters": [{"kind": "scale"}]},
            postprocess={"enabled": True, "filters": [{"kind": "sharpen"}]},
        )
    )
    steps = projection.steps

    assert [step.stage_name for step in steps] == [
        "01_preprocess",
        "02_super_resolution",
        "03_frame_interpolation",
        "04_postprocess",
    ]
    assert steps[1].algorithm_kwargs["tensor_backend"] == "paddle"
    assert steps[1].algorithm_kwargs["num_frames"] == 8
    assert steps[2].algorithm_kwargs["model_version"] == "4.25"


def test_stage_projection_resolves_workflow_without_mutating_input():
    workflow = _workflow()

    resolved, projection, final_output_fps = StageProjection.resolve_workflow(
        workflow,
        source_fps=24.0,
    )

    assert workflow["interpolation"]["multi"] == 2
    assert resolved["interpolation"]["multi"] == 3
    assert projection.steps[0].algorithm_kwargs["multi"] == 3
    assert final_output_fps == 60.0


def test_stage_plan_projects_interpolation_or_target_timeline():
    workflow = _workflow(fpsMode="multi")
    projection = StageProjection.from_workflow(workflow)

    source = make_video_metadata(12, duration=1.0)
    assert build_stage_plan(projection, source, output_fps=None).total_encoded_frames == 23
    assert build_stage_plan(projection, source, output_fps=60.0).total_encoded_frames == 60
