"""Shared immutable configuration for the raw stage-worker pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning import ResumeState, StagePlan
from app.ports.media import RawVideoPort
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_progress import StageProgressCallback


@dataclass(frozen=True, slots=True)
class WorkerPipelineRuntimeConfig:
    """Static state shared by the raw worker pipeline and chain runtime."""

    ffmpeg: RawVideoPort
    input_path: str
    decode_config: dict[str, Any]
    stage_plan: StagePlan
    progress_callbacks: list[StageProgressCallback]
    source_width: int
    source_height: int
    source_frames: int
    resume_state: ResumeState
    metrics: PipelineMetrics


__all__ = ["WorkerPipelineRuntimeConfig"]
