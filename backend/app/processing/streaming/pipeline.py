"""Streaming pipeline orchestrator.

Builds the stage plan + resume signature, runs the decode/process/encode
threads through :func:`run_streaming_pipeline`, and finalizes the
segmented output. Public entry point: :func:`process_video_streaming`.
"""

from __future__ import annotations

from typing import Any

from app.planning.resume_policy import ResumeMode
from app.ports.media import EncodeProgressCallback, MediaRuntimePort
from app.processing.streaming.pipeline_lifecycle import (
    finalize_streaming_output,
    prepare_streaming_manifest,
)
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_context import StreamingPipelineContext
from app.processing.streaming.pipeline_dispatch import run_streaming_pipeline
from app.processing.streaming.pipeline_context import StreamingPipelinePreflight
from app.processing.streaming.stage_worker_progress import StageProgressCallback
from app.processing.streaming.runtime_ports import ManifestFactoryPort, ResumeStatusSink, WorkerLogSink
from app.processing.execution_result import ExecutionResult


def process_video_streaming(
    *,
    ffmpeg: MediaRuntimePort,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    preflight: StreamingPipelinePreflight,
    progress_callbacks: list[StageProgressCallback],
    metrics: PipelineMetrics,
    manifest_factory: ManifestFactoryPort,
    resume_status_sink: ResumeStatusSink,
    worker_log_sink: WorkerLogSink,
    output_fps: float | None = None,
    encode_progress_callback: EncodeProgressCallback | None = None,
    resume_mode: ResumeMode = "auto",
) -> ExecutionResult:
    """Process a video through the selected streaming runtime."""
    manifest, resume_state = prepare_streaming_manifest(
        manifest=manifest_factory(output_path),
        signature=preflight.signature,
        config_snapshot=preflight.config_snapshot,
        resume_mode=resume_mode,
    )
    context = StreamingPipelineContext(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        preflight=preflight,
        manifest=manifest,
        resume_state=resume_state,
        progress_callbacks=progress_callbacks,
        output_fps=output_fps,
        encode_progress_callback=encode_progress_callback,
        metrics=metrics,
        manifest_factory=manifest_factory,
        resume_status_sink=resume_status_sink,
        worker_log_sink=worker_log_sink,
    )

    if resume_state.start_source_frame >= preflight.resume_source_frames:
        completed_output_frames = resume_state.completed_output_frames
    else:
        completed_output_frames = run_streaming_pipeline(context=context)

    return finalize_streaming_output(
        context=context,
        completed_output_frames=completed_output_frames,
    )
