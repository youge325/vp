"""Shared process/inspect preparation for one streaming pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.generated.contracts import RuntimeConfigBundle, WorkflowConfig
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import resolve_video_info
from app.planning.stage_projection import StageProjection
from app.planning.workflow_validation import validate_workflow_requirements
from app.planning.model_availability import ModelAvailabilityPort
from app.ports.media import MediaProbePort
from app.processing.streaming.pipeline_context import StreamingPipelinePreflight
from app.processing.streaming.pipeline_preflight import build_streaming_pipeline_preflight


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """Immutable validated facts required to execute or inspect one run."""

    output_path: str
    decode_config: dict[str, Any]
    encode_config: dict[str, Any]
    preflight: StreamingPipelinePreflight

    @property
    def processing_steps(self) -> tuple[ProcessingStep, ...]:
        return self.preflight.stage_plan.processing_steps

    @property
    def final_output_fps(self) -> float | None:
        return self.preflight.stage_plan.encoder_fps_override

    @property
    def expected_output_frames(self) -> int:
        return self.preflight.stage_plan.total_encoded_frames


def prepare_pipeline_preflight(
    *,
    ffmpeg: MediaProbePort,
    input_path: str,
    output_path: str,
    configs: RuntimeConfigBundle,
    model_availability: ModelAvailabilityPort,
) -> PreparedRun:
    """Resolve workflow projection and construct the shared immutable preflight."""
    video_info = resolve_video_info(ffmpeg, input_path)
    sections = configs.model_dump(by_alias=True, mode="json")
    workflow_config, projection, target_fps = StageProjection.resolve_workflow(
        sections["workflow"],
        source_fps=video_info.source_fps,
    )
    sections["workflow"] = WorkflowConfig.model_validate(workflow_config).model_dump(by_alias=True, mode="json")
    validate_workflow_requirements(projection.steps, model_availability)
    preflight = build_streaming_pipeline_preflight(
        video_info=video_info,
        input_path=input_path,
        output_path=output_path,
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=sections["workflow"],
        output_config=sections["output"],
        projection=projection,
        target_fps=target_fps,
    )
    return PreparedRun(
        output_path=output_path,
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        preflight=preflight,
    )


__all__ = ["PreparedRun", "prepare_pipeline_preflight"]
