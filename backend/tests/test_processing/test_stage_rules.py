from __future__ import annotations

import app.processing.streaming.stage_rules as stage_rules
from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.stage_rules import (
    ordered_steps,
    stage_output_dimensions,
    stage_output_frame_count,
    stage_tensor_backend_name,
)


def test_stage_rules_centralize_stage_order_dimensions_and_backend_selection() -> None:
    assert not hasattr(stage_rules, "super_resolution_changes_dimensions")
    assert not hasattr(stage_rules, "is_paddlegan_vsr_step")

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
