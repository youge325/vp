from __future__ import annotations

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.processing.streaming.stage_rules import (
    stage_tensor_backend_name,
)


def test_stage_rules_centralize_stage_order_and_backend_selection() -> None:
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
    stage_plan = build_stage_plan(StageProjection(tuple(steps)), 3, source_duration=1.0, output_fps=None)

    assert [step.stage_name for step in stage_plan.steps] == [
        "01_super_resolution",
        "02_frame_interpolation",
    ]
    assert stage_tensor_backend_name(steps[0]) == "paddle"
    assert stage_plan.projection.project_frame_count(steps[1], 3) == 7
