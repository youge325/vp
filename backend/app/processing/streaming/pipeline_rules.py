"""Pure pipeline-level planning rules for streaming execution."""

from __future__ import annotations

from typing import Any

from app.planning import StagePlan
from app.processing.streaming.stage_rules import (
    ordered_steps,
    resolve_stage_plan_output_dimensions,
    stage_output_fps,
    stage_output_frame_count,
    stage_requires_file_pipeline,
)


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
    return stage_output_fps(interpolation_step, source_fps)


def resolved_output_dimensions(
    *,
    video_info: dict[str, Any],
    stage_plan: StagePlan,
) -> tuple[int, int]:
    width = int(video_info["width"])
    height = int(video_info["height"])
    return resolve_stage_plan_output_dimensions(
        stage_plan,
        source_width=width,
        source_height=height,
    )


__all__ = [
    "resolved_output_dimensions",
    "resolved_stream_fps",
    "should_use_stage_file_pipeline",
    "stage_file_resume_source_frames",
]
