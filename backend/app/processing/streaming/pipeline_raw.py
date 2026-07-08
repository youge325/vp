"""Rawvideo worker-chain runtime for streaming pipeline execution."""

from __future__ import annotations

from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_runtime import StageWorkerRunner, run_raw_pipeline_runtime
from app.processing.streaming.pipeline_rules import resolved_stream_fps
from app.utils.ffmpeg import FFmpegWrapper


def run_raw_streaming_pipeline(
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
    output_path: str,
    output_fps: float | None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
    stage_worker_runner: StageWorkerRunner | None = None,
) -> int:
    return run_raw_pipeline_runtime(
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
        stream_fps=resolved_stream_fps(video_info["source_fps"], stage_plan),
        resume_state=resume_state,
        segment_frames=segment_frames,
        output_path=output_path,
        output_fps=output_fps,
        encode_progress_callback=encode_progress_callback,
        metrics=metrics,
        stage_worker_runner=stage_worker_runner,
    )


__all__ = ["run_raw_streaming_pipeline"]
