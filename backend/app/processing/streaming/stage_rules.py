"""Pure stage-planning rules shared by streaming execution modes."""

from __future__ import annotations

from typing import Any

from app.planning import ProcessingStep, StagePlan


def stage_tensor_backend_name(step: ProcessingStep) -> str | None:
    if step.algorithm_type == "frame_filter_chain":
        return None
    backend_name = step.algorithm_kwargs.get("tensor_backend")
    if not isinstance(backend_name, str) or not backend_name:
        raise ValueError(f"Stage '{step.stage_name}' requires an explicit tensor backend.")
    return backend_name


def algorithm_kwargs_for_create(step: ProcessingStep) -> dict[str, Any]:
    return {key: value for key, value in step.algorithm_kwargs.items() if key != "tensor_backend"}


def stage_progress_total(step: ProcessingStep, input_frame_count: int, output_frame_count: int) -> int:
    if step.algorithm_type == "frame_interpolation":
        return max(input_frame_count - 1, 1)
    return max(output_frame_count, 1)


def stage_output_dimensions(
    step: ProcessingStep,
    *,
    input_width: int,
    input_height: int,
) -> tuple[int, int]:
    if step.algorithm_type != "super_resolution":
        return input_width, input_height
    if not _super_resolution_changes_dimensions(step):
        return input_width, input_height
    scale_factor = float(step.algorithm_kwargs["scale_factor"])
    return (
        max(1, int(round(input_width * scale_factor))),
        max(1, int(round(input_height * scale_factor))),
    )


def resolve_stage_plan_output_dimensions(
    stage_plan: StagePlan,
    *,
    source_width: int,
    source_height: int,
) -> tuple[int, int]:
    width = source_width
    height = source_height
    for step in stage_plan.steps:
        width, height = stage_output_dimensions(step, input_width=width, input_height=height)
    return width, height


def stage_requires_file_pipeline(step: ProcessingStep) -> bool:
    return step.descriptor.requires_file_pipeline


def _super_resolution_changes_dimensions(step: ProcessingStep) -> bool:
    if step.algorithm_type != "super_resolution":
        return False
    return step.descriptor.changes_dimensions


__all__ = [
    "algorithm_kwargs_for_create",
    "resolve_stage_plan_output_dimensions",
    "stage_output_dimensions",
    "stage_progress_total",
    "stage_requires_file_pipeline",
    "stage_tensor_backend_name",
]
