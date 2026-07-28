"""Shared process/inspect preparation for one streaming pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.cli.runtime_configs import RuntimeConfigs
from app.models import WorkflowConfig
from app.planning import (
    ProcessingStep,
    StageProjection,
    resolve_video_info,
)
from app.ports.media import MediaProbePort
from app.processing.streaming.pipeline_context import StreamingPipelinePreflight
from app.processing.streaming.pipeline_preflight import build_streaming_pipeline_preflight


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """Immutable validated facts required to execute or inspect one run."""

    output_path: str
    runtime_configs: RuntimeConfigs
    preflight: StreamingPipelinePreflight

    @property
    def processing_steps(self) -> tuple[ProcessingStep, ...]:
        return self.preflight.stage_plan.steps

    @property
    def final_output_fps(self) -> float | None:
        return self.preflight.stage_plan.output_fps

    @property
    def expected_output_frames(self) -> int:
        return self.preflight.stage_plan.total_encoded_frames


def prepare_pipeline_preflight(
    *,
    ffmpeg: MediaProbePort,
    input_path: str,
    output_path: str,
    configs: RuntimeConfigs,
) -> PreparedRun:
    """Resolve workflow projection and construct the shared immutable preflight."""
    video_info = resolve_video_info(ffmpeg, input_path)
    workflow_config, projection, final_output_fps = StageProjection.resolve_workflow(
        configs.json_section("workflow"),
        source_fps=video_info.source_fps,
    )
    resolved_configs = configs.with_workflow(WorkflowConfig.model_validate(workflow_config))
    sections = resolved_configs.json_sections()
    preflight = build_streaming_pipeline_preflight(
        video_info=video_info,
        input_path=input_path,
        output_path=output_path,
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=sections["workflow"],
        output_config=sections["output"],
        projection=projection,
        output_fps=final_output_fps,
    )
    return PreparedRun(
        output_path=output_path,
        runtime_configs=resolved_configs,
        preflight=preflight,
    )


__all__ = ["PreparedRun", "prepare_pipeline_preflight"]
