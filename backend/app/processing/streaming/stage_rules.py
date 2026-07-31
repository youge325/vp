"""Pure stage-planning rules shared by streaming execution modes."""

from __future__ import annotations

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import StagePlan


def stage_tensor_backend_name(step: ProcessingStep) -> str | None:
    if step.algorithm_type == "frame_filter_chain":
        return None
    backend_name = step.algorithm_kwargs.get("tensor_backend")
    if not isinstance(backend_name, str) or not backend_name:
        raise ValueError(f"Stage '{step.stage_name}' requires an explicit tensor backend.")
    return backend_name


def stage_progress_total(step: ProcessingStep, input_frame_count: int, output_frame_count: int) -> int:
    if step.algorithm_type == "frame_interpolation":
        return max(input_frame_count - 1, 1)
    return max(output_frame_count, 1)


def resolve_stage_plan_output_dimensions(
    stage_plan: StagePlan,
    *,
    source_width: int,
    source_height: int,
) -> tuple[int, int]:
    return stage_plan.projection.output_dimensions(source_width, source_height)


def stage_requires_file_pipeline(step: ProcessingStep) -> bool:
    return step.descriptor.requires_file_pipeline


__all__ = [
    "resolve_stage_plan_output_dimensions",
    "stage_progress_total",
    "stage_requires_file_pipeline",
    "stage_tensor_backend_name",
]
