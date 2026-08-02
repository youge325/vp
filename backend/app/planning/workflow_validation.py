"""Pure stage validation with an injected model-availability boundary."""

from __future__ import annotations

from collections.abc import Sequence

from app.catalog.algorithm_capabilities import find_static_algorithm_capability
from app.catalog.tensor_capabilities import supports_backend_engine
from app.errors.codes import TaskErrorCode
from app.errors.process import raise_error
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


def _required_int(step: ProcessingStep, key: str) -> int:
    value = step.algorithm_kwargs.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Stage '{step.stage_name}' requires an integer '{key}' value.",
            details={"stage": step.stage_name, "field": key},
        )
    return value


def _validate_structure(step: ProcessingStep) -> None:
    if step.algorithm_type == "frame_filter_chain":
        return

    backend_name = _required_string(step, "tensor_backend")
    engine = _required_string(step, "engine")
    if not supports_backend_engine(backend_name, engine):
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Tensor backend '{backend_name}' does not support engine '{engine}'.",
            details={"stage": step.stage_name, "tensor_backend": backend_name, "engine": engine},
        )
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
        model_version = _required_string(step, "model_version")
        capability = find_static_algorithm_capability(step.algorithm_type, algorithm)
        if capability is None or model_version not in capability.models:
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"Unsupported RIFE model version: '{model_version}'.",
                details={"stage": step.stage_name, "model_version": model_version},
            )
        return

    algorithm = _required_string(step, "sr_algorithm")
    capability = find_static_algorithm_capability(step.algorithm_type, algorithm)
    if capability is not None and capability.scale_factors:
        scale_factor = _required_float(step, "scale_factor")
        if scale_factor not in capability.scale_factors:
            supported = ", ".join(f"{value}x" for value in capability.scale_factors)
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"{algorithm} supports only {supported} super-resolution; got {scale_factor:g}x.",
                details={
                    "stage": step.stage_name,
                    "algorithm": algorithm,
                    "scale_factor": scale_factor,
                },
            )
    if capability is not None and capability.input_frame_mode == "fixed_window":
        num_frames = _required_int(step, "num_frames")
        if num_frames != capability.default_num_frames:
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"{algorithm} requires a fixed {capability.default_num_frames}-frame window; got {num_frames}.",
                details={
                    "stage": step.stage_name,
                    "algorithm": algorithm,
                    "num_frames": num_frames,
                },
            )
    if descriptor.model_kind == "pytorch_vsr" and engine != "cuda":
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"{algorithm} supports only the CUDA engine; got '{engine}'.",
            details={"stage": step.stage_name, "algorithm": algorithm, "engine": engine},
        )
    if backend_name not in descriptor.supported_backends:
        if descriptor.model_kind == "paddlegan_vsr":
            message = f"PaddleGAN VSR requires the Paddle tensor backend; got '{backend_name}'."
        elif descriptor.model_kind == "pytorch_vsr":
            message = f"{algorithm} requires the PyTorch tensor backend; got '{backend_name}'."
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
