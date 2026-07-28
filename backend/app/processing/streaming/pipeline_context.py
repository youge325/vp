"""Immutable planning and execution contexts for the streaming pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_progress import StageProgressCallback
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.ffmpeg._progress import EncodeProgressCallback


@dataclass(frozen=True, slots=True)
class StreamingPipelinePreflight:
    video_info: dict[str, Any]
    stage_plan: StagePlan
    signature: str
    config_snapshot: dict[str, Any]
    use_stage_file_pipeline: bool
    resume_source_frames: int
    output_width: int
    output_height: int
    segment_frames: int


@dataclass(frozen=True, slots=True)
class StreamingPipelineContext:
    ffmpeg: FFmpegWrapper
    input_path: str
    output_path: str
    decode_config: dict[str, Any]
    encode_config: dict[str, Any]
    preflight: StreamingPipelinePreflight
    manifest: SegmentManifest
    resume_state: ResumeState
    tensor_backend_name: str
    progress_callbacks: list[StageProgressCallback]
    output_fps: float | None
    encode_progress_callback: EncodeProgressCallback | None
    metrics: PipelineMetrics


__all__ = ["StreamingPipelineContext", "StreamingPipelinePreflight"]
