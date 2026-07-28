"""Pure pipeline-level planning rules for streaming execution."""

from __future__ import annotations

from app.planning import StagePlan
from app.ports.media import VideoMetadata
from app.processing.streaming.stage_rules import (
    resolve_stage_plan_output_dimensions,
    stage_requires_file_pipeline,
)


def should_use_stage_file_pipeline(stage_plan: StagePlan) -> bool:
    return any(stage_requires_file_pipeline(step) for step in stage_plan.steps)


def stage_file_resume_source_frames(stage_plan: StagePlan, source_frames: int) -> int:
    """Return the source-frame domain used by the final staged manifest."""
    return stage_plan.projection.output_frame_count(
        max(int(source_frames), 0),
        stop_before=max(len(stage_plan.steps) - 1, 0),
    )


def resolved_stream_fps(source_fps: float, stage_plan: StagePlan) -> float:
    return stage_plan.projection.output_fps(source_fps)


def resolved_output_dimensions(
    *,
    video_info: VideoMetadata,
    stage_plan: StagePlan,
) -> tuple[int, int]:
    width = video_info.width
    height = video_info.height
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
