"""Shared immutable configuration for the raw streaming encoder runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.metrics import PipelineMetrics
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.ffmpeg._progress import EncodeProgressCallback


@dataclass(frozen=True, slots=True)
class EncoderRuntimeConfig:
    """Static encoder state shared by the raw pipeline, worker, and writer."""

    ffmpeg: FFmpegWrapper
    encode_config: dict[str, Any]
    manifest: SegmentManifest
    width: int
    height: int
    fps: float
    output_fps: float | None
    segment_frames: int
    resume_state: ResumeState
    output_path: str
    encode_progress_callback: EncodeProgressCallback | None
    metrics: PipelineMetrics


__all__ = ["EncoderRuntimeConfig"]
