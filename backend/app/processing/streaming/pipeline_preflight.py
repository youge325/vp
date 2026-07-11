"""Preflight context assembly for the streaming pipeline entry point."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning import (
    ProcessingStepInput,
    StagePlan,
    build_signature,
    build_stage_plan,
    normalize_processing_steps,
    resolve_video_info,
)
from app.processing.streaming.pipeline_rules import (
    build_config_snapshot,
    resolved_output_dimensions,
    should_use_stage_file_pipeline,
    stage_file_resume_source_frames,
)
from app.utils.ffmpeg import FFmpegWrapper


@dataclass(slots=True)
class _StreamingPipelinePreflight:
    video_info: dict[str, Any]
    stage_plan: StagePlan
    signature: str
    config_snapshot: dict[str, Any]
    use_stage_file_pipeline: bool
    resume_source_frames: int
    output_width: int
    output_height: int
    segment_frames: int


def build_streaming_pipeline_preflight(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[ProcessingStepInput],
    output_fps: float | None,
) -> _StreamingPipelinePreflight:
    resolved_steps = normalize_processing_steps(processing_steps)
    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        resolved_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=output_fps,
    )
    signature = build_signature(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=resolved_steps,
        video_info=video_info,
    )
    config_snapshot = build_config_snapshot(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=resolved_steps,
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

    return _StreamingPipelinePreflight(
        video_info=video_info,
        stage_plan=stage_plan,
        signature=signature,
        config_snapshot=config_snapshot,
        use_stage_file_pipeline=use_stage_file_pipeline,
        resume_source_frames=resume_source_frames,
        output_width=output_width,
        output_height=output_height,
        segment_frames=max(1, int(output_config.get("segmentFrames") or 1000)),
    )


__all__ = ["build_streaming_pipeline_preflight"]
