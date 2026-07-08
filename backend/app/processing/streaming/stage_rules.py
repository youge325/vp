"""Pure stage-planning rules shared by streaming execution modes."""

from __future__ import annotations

from typing import Any

from app.planning import ProcessingStep, StagePlan


def ordered_steps(stage_plan: StagePlan) -> list[ProcessingStep]:
    """Return the execution-order steps from a resolved stage plan."""
    steps = list(stage_plan.pre_steps)
    if stage_plan.interpolation_step is not None:
        steps.append(stage_plan.interpolation_step)
    steps.extend(stage_plan.post_steps)
    return steps


def stage_tensor_backend_name(step: ProcessingStep, default_backend_name: str) -> str:
    return str(step.algorithm_kwargs.get("tensor_backend") or default_backend_name)


def algorithm_kwargs_for_create(step: ProcessingStep) -> dict[str, Any]:
    return {key: value for key, value in step.algorithm_kwargs.items() if key != "tensor_backend"}


def stage_output_frame_count(step: ProcessingStep, input_frame_count: int) -> int:
    if step.algorithm_type != "frame_interpolation":
        return input_frame_count
    if input_frame_count < 2:
        return input_frame_count
    multi = int(step.algorithm_kwargs.get("multi") or 2)
    return input_frame_count + (input_frame_count - 1) * (multi - 1)


def stage_output_fps(step: ProcessingStep, input_fps: float) -> float:
    if step.algorithm_type != "frame_interpolation":
        return input_fps
    multi = int(step.algorithm_kwargs.get("multi") or 2)
    return input_fps * multi


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
    scale_factor = float(step.algorithm_kwargs.get("scale_factor") or 1.0)
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
    for step in ordered_steps(stage_plan):
        width, height = stage_output_dimensions(step, input_width=width, input_height=height)
    return width, height


def stage_requires_file_pipeline(step: ProcessingStep) -> bool:
    if step.algorithm_type == "frame_interpolation":
        return True
    return step.algorithm_type == "super_resolution" and _is_paddlegan_vsr_step(step)


def _super_resolution_changes_dimensions(step: ProcessingStep) -> bool:
    if step.algorithm_type != "super_resolution":
        return False
    if step.algorithm_kwargs.get("onnx_model"):
        return True
    return _is_paddlegan_vsr_step(step)


def _is_paddlegan_vsr_step(step: ProcessingStep) -> bool:
    sr_algorithm = str(step.algorithm_kwargs.get("sr_algorithm") or "")
    try:
        from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS
    except Exception:
        return False
    return sr_algorithm in PADDLEGAN_VSR_SPECS


__all__ = [
    "algorithm_kwargs_for_create",
    "ordered_steps",
    "resolve_stage_plan_output_dimensions",
    "stage_output_dimensions",
    "stage_output_fps",
    "stage_output_frame_count",
    "stage_progress_total",
    "stage_requires_file_pipeline",
    "stage_tensor_backend_name",
]
