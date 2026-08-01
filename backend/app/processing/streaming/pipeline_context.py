"""Immutable planning and execution contexts for the streaming pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning.manifest import ResumeState, SegmentManifest
from app.planning.stage_plan import StagePlan
from app.ports.media import EncodeProgressCallback, MediaRuntimePort
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.runtime_ports import ManifestFactoryPort, ResumeStatusSink, WorkerLogSink
from app.processing.streaming.stage_worker_progress import StageProgressCallback


@dataclass(frozen=True, slots=True)
class StreamingPipelinePreflight:
    stage_plan: StagePlan
    signature: str
    config_snapshot: dict[str, Any]
    segment_frames: int


@dataclass(frozen=True, slots=True)
class StreamingPipelineContext:
    ffmpeg: MediaRuntimePort
    input_path: str
    output_path: str
    decode_config: dict[str, Any]
    encode_config: dict[str, Any]
    preflight: StreamingPipelinePreflight
    manifest: SegmentManifest
    resume_state: ResumeState
    progress_callbacks: list[StageProgressCallback]
    encode_progress_callback: EncodeProgressCallback | None
    metrics: PipelineMetrics
    manifest_factory: ManifestFactoryPort
    resume_status_sink: ResumeStatusSink
    worker_log_sink: WorkerLogSink


__all__ = ["StreamingPipelineContext", "StreamingPipelinePreflight"]
