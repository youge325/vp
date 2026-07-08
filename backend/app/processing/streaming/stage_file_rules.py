"""Small pure rules for file-backed stage pipeline orchestration."""

from __future__ import annotations

import json
import os

from app.planning import ProcessingStep
from app.planning.manifest import ResumeState


def empty_resume_state() -> ResumeState:
    return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])


def stage_signature(stage_position: int, step: ProcessingStep, input_path: str, output_path: str) -> str:
    return json.dumps(
        {
            "stage": stage_position,
            "step": step.to_jsonable(),
            "input": os.path.abspath(input_path),
            "output": os.path.abspath(output_path),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def safe_stage_name(step: ProcessingStep) -> str:
    name = step.stage_name or step.algorithm_type or "stage"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)


__all__ = [
    "empty_resume_state",
    "safe_stage_name",
    "stage_signature",
]
