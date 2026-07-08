"""Stage-file/raw dispatch for streaming pipeline execution."""

from __future__ import annotations

from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_lifecycle import emit_resume_status_event
from app.processing.streaming.pipeline_raw import run_raw_streaming_pipeline
from app.processing.streaming.stage_file_pipeline import run_stage_file_pipeline
from app.utils.ffmpeg import FFmpegWrapper


def run_streaming_pipeline(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    video_info: dict[str, Any],
    output_width: int,
    output_height: int,
    resume_state: ResumeState,
    segment_frames: int,
    use_stage_file_pipeline: bool,
    output_path: str,
    output_fps: float | None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
) -> int:
    if use_stage_file_pipeline:
        emit_resume_status_event(
            resume_state=resume_state,
            total_output_frames=stage_plan.total_encoded_frames,
        )
        return run_stage_file_pipeline(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            encode_config=encode_config,
            manifest=manifest,
            stage_plan=stage_plan,
            tensor_backend_name=tensor_backend_name,
            progress_callbacks=progress_callbacks,
            video_info=video_info,
            resume_state=resume_state,
            segment_frames=segment_frames,
            output_path=output_path,
            output_fps=output_fps,
            metrics=metrics,
        )

    emit_resume_status_event(
        resume_state=resume_state,
        total_output_frames=stage_plan.total_encoded_frames,
    )

    return run_raw_streaming_pipeline(
        ffmpeg=ffmpeg,
        input_path=input_path,
        decode_config=decode_config,
        encode_config=encode_config,
        manifest=manifest,
        signature=signature,
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
        progress_callbacks=progress_callbacks,
        video_info=video_info,
        output_width=output_width,
        output_height=output_height,
        resume_state=resume_state,
        segment_frames=segment_frames,
        output_path=output_path,
        output_fps=output_fps,
        encode_progress_callback=encode_progress_callback,
        metrics=metrics,
    )


__all__ = ["run_streaming_pipeline"]
