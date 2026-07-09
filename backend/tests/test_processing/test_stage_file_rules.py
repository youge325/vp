from __future__ import annotations

from app.planning import ProcessingStep
from app.processing.streaming.stage_file_rules import (
    empty_resume_state,
    safe_stage_name,
    stage_signature,
)


def test_stage_file_rules_build_safe_signature_and_empty_resume(tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01 super/resolution",
    )

    signature = stage_signature(2, step, "input.mp4", str(tmp_path / "stage.mp4"))
    resume_state = empty_resume_state()

    assert safe_stage_name(step) == "01_super_resolution"
    assert '"stage": 2' in signature
    assert '"input":' in signature
    assert resume_state.start_source_frame == 0
    assert resume_state.completed_output_frames == 0
    assert resume_state.completed_segments == []
