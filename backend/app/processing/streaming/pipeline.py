"""Streaming pipeline orchestrator.

Builds the stage plan + resume signature, runs the decode/process/encode
threads through :func:`run_streaming_pipeline`, and finalizes the
segmented output. Public entry point: :func:`process_video_streaming`.
"""

from __future__ import annotations

from typing import Any, Callable

from app.planning import (
    ProcessingStepInput,
    ResumeMode,
)
from app.processing.streaming.pipeline_lifecycle import (
    finalize_streaming_output,
    prepare_streaming_manifest,
)
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_dispatch import run_streaming_pipeline
from app.processing.streaming.pipeline_preflight import build_streaming_pipeline_preflight
from app.utils.ffmpeg import FFmpegWrapper


def process_video_streaming(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[ProcessingStepInput],
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    output_fps: float | None = None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None = None,
    resume_mode: ResumeMode = "auto",
    metrics: PipelineMetrics | None = None,
) -> dict[str, Any]:
    """Process a video without writing temporary frames to disk."""
    if metrics is None:
        # Standalone caller (tests, smoke scripts) — keep the call site
        # simple by self-provisioning metrics that nobody reads.
        metrics = PipelineMetrics()
    preflight = build_streaming_pipeline_preflight(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        tensor_backend_name=tensor_backend_name,
        output_fps=output_fps,
    )

    manifest, resume_state = prepare_streaming_manifest(
        output_path=output_path,
        signature=preflight.signature,
        config_snapshot=preflight.config_snapshot,
        resume_mode=resume_mode,
    )

    if resume_state.start_source_frame >= preflight.resume_source_frames:
        completed_output_frames = resume_state.completed_output_frames
    else:
        completed_output_frames = run_streaming_pipeline(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            encode_config=encode_config,
            manifest=manifest,
            signature=preflight.signature,
            stage_plan=preflight.stage_plan,
            tensor_backend_name=tensor_backend_name,
            progress_callbacks=progress_callbacks,
            video_info=preflight.video_info,
            output_width=preflight.output_width,
            output_height=preflight.output_height,
            resume_state=resume_state,
            segment_frames=preflight.segment_frames,
            use_stage_file_pipeline=preflight.use_stage_file_pipeline,
            output_path=output_path,
            output_fps=output_fps,
            encode_progress_callback=encode_progress_callback,
            metrics=metrics,
        )

    return finalize_streaming_output(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        encode_config=encode_config,
        manifest=manifest,
        signature=preflight.signature,
        completed_output_frames=completed_output_frames,
        total_output_frames=preflight.stage_plan.total_encoded_frames,
        strict_total_frames=output_fps is None,
    )
