"""Preflight context assembly for the streaming pipeline entry point."""

from __future__ import annotations

from typing import Any

from app.planning import (
    ProcessingStep,
    build_run_identity,
    build_stage_plan,
    resolve_video_info,
)
from app.processing.streaming.pipeline_context import StreamingPipelinePreflight
from app.processing.streaming.pipeline_rules import (
    resolved_output_dimensions,
    should_use_stage_file_pipeline,
    stage_file_resume_source_frames,
)
from app.utils.ffmpeg import FFmpegWrapper


def build_streaming_pipeline_preflight(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[ProcessingStep],
    output_fps: float | None,
) -> StreamingPipelinePreflight:
    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        processing_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=output_fps,
    )
    identity = build_run_identity(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        video_info=video_info,
    )
    use_stage_file_pipeline = should_use_stage_file_pipeline(stage_plan)
    resume_source_frames = (
        stage_file_resume_source_frames(stage_plan, int(video_info["source_frames"]))
        if use_stage_file_pipeline
        else int(video_info["source_frames"])
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
        segment_frames=max(1, int(output_config.get("segmentFrames") or 1000)),
    )


__all__ = ["build_streaming_pipeline_preflight"]
