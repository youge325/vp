"""Shared immutable configuration for the raw streaming encoder runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning.manifest import ResumeState, SegmentManifest
from app.ports.media import EncodeProgressCallback, EncodingMediaPort
from app.processing.streaming.metrics import PipelineMetrics


@dataclass(frozen=True, slots=True)
class EncoderRuntimeConfig:
    """Static encoder state shared by the raw pipeline, worker, and writer."""

    ffmpeg: EncodingMediaPort
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
