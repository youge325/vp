"""Pure pipeline-level planning rules for streaming execution."""

from __future__ import annotations

import os
from typing import Any

from app.planning import ProcessingStepInput, StagePlan, processing_steps_to_jsonable
from app.processing.streaming.stage_rules import (
    ordered_steps,
    resolve_stage_plan_output_dimensions,
    stage_output_frame_count,
    stage_requires_file_pipeline,
)


def build_config_snapshot(
    *,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[ProcessingStepInput],
    video_info: dict[str, Any],
) -> dict[str, Any]:
    """Capture the parameters that determine signature + behavior for a run."""
    return {
        "input_path": os.path.abspath(input_path),
        "output_path": os.path.abspath(output_path),
        "decode_config": decode_config,
        "encode_config": encode_config,
        "workflow_config": workflow_config,
        "output_config": {
            "segmentFrames": max(1, int(output_config.get("segmentFrames") or 1000)),
        },
        "processing_steps": processing_steps_to_jsonable(processing_steps),
        "video_info": {
            "width": video_info["width"],
            "height": video_info["height"],
            "source_fps": video_info["source_fps"],
            "source_frames": video_info["source_frames"],
        },
    }


def should_use_stage_file_pipeline(stage_plan: StagePlan) -> bool:
    return any(stage_requires_file_pipeline(step) for step in ordered_steps(stage_plan))


def stage_file_resume_source_frames(stage_plan: StagePlan, source_frames: int) -> int:
    """Return the source-frame domain used by the final staged manifest."""
    current_frames = max(int(source_frames), 0)
    steps = ordered_steps(stage_plan)
    for step in steps[:-1]:
        current_frames = stage_output_frame_count(step, current_frames)
    return current_frames


def resolved_stream_fps(source_fps: float, stage_plan: StagePlan) -> float:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        return source_fps
    multi = int(interpolation_step.algorithm_kwargs.get("multi") or 2)
    return source_fps * multi


def resolved_output_dimensions(
    *,
    video_info: dict[str, Any],
    stage_plan: StagePlan,
    tensor_backend_name: str,
) -> tuple[int, int]:
    width = int(video_info["width"])
    height = int(video_info["height"])
    del tensor_backend_name
    return resolve_stage_plan_output_dimensions(
        stage_plan,
        source_width=width,
        source_height=height,
    )


__all__ = [
    "build_config_snapshot",
    "resolved_output_dimensions",
    "resolved_stream_fps",
    "should_use_stage_file_pipeline",
    "stage_file_resume_source_frames",
]
