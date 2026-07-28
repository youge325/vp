"""Shared immutable configuration for one stage-file runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning import ProcessingStep
from app.ports.media import StageFileMediaPort
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_progress import StageProgressCallback


@dataclass(frozen=True, slots=True)
class StageFileRuntimeConfig:
    """Static state shared by a stage's chunk planner, runtime, and encoder."""

    ffmpeg: StageFileMediaPort
    input_path: str
    decode_config: dict[str, Any]
    encode_config: dict[str, Any]
    step: ProcessingStep
    stage_index: int
    stage_total: int
    tensor_backend_name: str | None
    progress_callback: StageProgressCallback | None
    input_width: int
    input_height: int
    output_width: int
    output_height: int
    output_fps: float
    encode_output_fps: float | None
    metrics: PipelineMetrics


__all__ = ["StageFileRuntimeConfig"]
