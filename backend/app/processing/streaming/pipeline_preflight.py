"""Preflight context assembly for the streaming pipeline entry point."""

from __future__ import annotations

from typing import Any

from app.planning.run_identity import build_run_identity
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.pipeline_context import StreamingPipelinePreflight
from app.processing.streaming.pipeline_rules import (
    resolved_output_dimensions,
    should_use_stage_file_pipeline,
    stage_file_resume_source_frames,
)


def build_streaming_pipeline_preflight(
    *,
    video_info: VideoMetadata,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    projection: StageProjection,
    output_fps: float | None,
) -> StreamingPipelinePreflight:
    stage_plan = build_stage_plan(
        projection,
        video_info.source_frames,
        source_duration=video_info.duration,
        output_fps=output_fps,
    )
    identity = build_run_identity(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=projection.steps,
        video_info=video_info,
    )
    use_stage_file_pipeline = should_use_stage_file_pipeline(stage_plan)
    resume_source_frames = (
        stage_file_resume_source_frames(stage_plan, video_info.source_frames)
        if use_stage_file_pipeline
        else video_info.source_frames
    )
    output_width, output_height = resolved_output_dimensions(
        video_info=video_info,
        stage_plan=stage_plan,
    )

    return StreamingPipelinePreflight(
        video_info=video_info,
        stage_plan=stage_plan,
        signature=identity.signature,
        config_snapshot=identity.config_snapshot,
        use_stage_file_pipeline=use_stage_file_pipeline,
        resume_source_frames=resume_source_frames,
        output_width=output_width,
        output_height=output_height,
        segment_frames=int(output_config["segmentFrames"]),
    )


__all__ = ["build_streaming_pipeline_preflight"]
