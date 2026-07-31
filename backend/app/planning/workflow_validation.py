"""Pure stage validation with an injected model-availability boundary."""

from __future__ import annotations

from collections.abc import Sequence

from app.errors import TaskErrorCode, raise_error
from app.planning.model_availability import ModelAvailabilityPort
from app.planning.processing_steps import ProcessingStep


def _required_string(step: ProcessingStep, key: str) -> str:
    value = step.algorithm_kwargs.get(key)
    if not isinstance(value, str) or not value:
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Stage '{step.stage_name}' requires a non-empty '{key}' value.",
            details={"stage": step.stage_name, "field": key},
        )
    return value


def _required_float(step: ProcessingStep, key: str) -> float:
    value = step.algorithm_kwargs.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Stage '{step.stage_name}' requires a numeric '{key}' value.",
            details={"stage": step.stage_name, "field": key},
        )
    return float(value)


def _validate_structure(step: ProcessingStep) -> None:
    if step.algorithm_type == "frame_filter_chain":
        return

    backend_name = _required_string(step, "tensor_backend")
    descriptor = step.descriptor
    if step.algorithm_type == "frame_interpolation":
        algorithm = _required_string(step, "algorithm")
        if algorithm != descriptor.factory_key:
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"Unsupported interpolation algorithm: '{algorithm}'.",
                details={"stage": step.stage_name, "algorithm": algorithm},
            )
        if backend_name not in descriptor.supported_backends:
            backend_label = "Paddle" if backend_name == "paddle" else f"'{backend_name}'"
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"RIFE interpolation does not support the {backend_label} tensor backend.",
                details={
                    "stage": step.stage_name,
                    "algorithm": algorithm,
                    "tensor_backend": backend_name,
                },
            )
        if backend_name == "pytorch":
            _required_string(step, "model_version")
        return

    algorithm = _required_string(step, "sr_algorithm")
    if descriptor.fixed_scale_factor is not None:
        scale_factor = _required_float(step, "scale_factor")
        if scale_factor != descriptor.fixed_scale_factor:
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"PaddleGAN VSR models are fixed 4x super-resolution models; got {scale_factor:g}x.",
                details={
                    "stage": step.stage_name,
                    "algorithm": algorithm,
                    "scale_factor": scale_factor,
                },
            )
    if backend_name not in descriptor.supported_backends:
        if descriptor.model_kind == "paddlegan_vsr":
            message = f"PaddleGAN VSR requires the Paddle tensor backend; got '{backend_name}'."
        else:
            message = f"ONNX super-resolution does not support the '{backend_name}' tensor backend."
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            message,
            details={
                "stage": step.stage_name,
                "algorithm": algorithm,
                "tensor_backend": backend_name,
            },
        )


def validate_workflow_requirements(
    processing_steps: Sequence[ProcessingStep],
    model_availability: ModelAvailabilityPort,
) -> None:
    """Validate structure first, then delegate external model checks."""
    for step in processing_steps:
        _validate_structure(step)
        if step.algorithm_type != "frame_filter_chain":
            model_availability.validate(step)


__all__ = ["validate_workflow_requirements"]
