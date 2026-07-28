"""Per-stage backend compatibility and model availability validation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from app.config import settings
from app.errors import TaskErrorCode, raise_error
from app.planning.processing_steps import ProcessingStep
from app.utils.onnx_models import resolve_onnx_model_path

_OnnxKind = Literal["interpolation", "super_resolution"]


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


def _missing_onnx_model(
    *,
    step: ProcessingStep,
    backend_name: str,
    algorithm: str,
    kind: _OnnxKind,
    model_name: str | None,
) -> None:
    try:
        resolve_onnx_model_path(
            kind,
            algorithm,
            model_name,
            model_root=settings.RIFE_MODEL_DIR,
        )
    except FileNotFoundError as exc:
        raise_error(
            TaskErrorCode.MISSING_MODEL,
            str(exc),
            details={
                "stage": step.stage_name,
                "algorithm": algorithm,
                "tensor_backend": backend_name,
                "model_root": settings.RIFE_MODEL_DIR,
            },
        )


def _validate_interpolation(step: ProcessingStep) -> None:
    backend_name = _required_string(step, "tensor_backend")
    algorithm = _required_string(step, "algorithm")
    if algorithm != "rife":
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Unsupported interpolation algorithm: '{algorithm}'.",
            details={"stage": step.stage_name, "algorithm": algorithm},
        )
    if backend_name not in {"pytorch", "onnx"}:
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

    if backend_name == "onnx":
        model_name = step.algorithm_kwargs.get("onnx_model")
        _missing_onnx_model(
            step=step,
            backend_name=backend_name,
            algorithm=algorithm,
            kind="interpolation",
            model_name=model_name if isinstance(model_name, str) else None,
        )
        return

    model_version = _required_string(step, "model_version")
    model_path = Path(settings.RIFE_MODEL_DIR) / f"flownet_v{model_version}.pkl"
    if not model_path.is_file() or model_path.stat().st_size == 0:
        raise_error(
            TaskErrorCode.MISSING_MODEL,
            f"Interpolation model is missing: {model_path}",
            details={
                "stage": step.stage_name,
                "algorithm": algorithm,
                "tensor_backend": backend_name,
                "model_path": str(model_path),
                "model_version": model_version,
            },
        )


def _validate_super_resolution(step: ProcessingStep) -> None:
    from app.algorithms.paddle.paddlegan_vsr.weights import ensure_paddlegan_vsr_weights

    backend_name = _required_string(step, "tensor_backend")
    algorithm = _required_string(step, "sr_algorithm")
    if algorithm in PADDLEGAN_VSR_SPECS:
        scale_factor = _required_float(step, "scale_factor")
        if scale_factor != 4.0:
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"PaddleGAN VSR models are fixed 4x super-resolution models; got {scale_factor:g}x.",
                details={
                    "stage": step.stage_name,
                    "algorithm": algorithm,
                    "scale_factor": scale_factor,
                },
            )
        if backend_name != "paddle":
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"PaddleGAN VSR requires the Paddle tensor backend; got '{backend_name}'.",
                details={
                    "stage": step.stage_name,
                    "algorithm": algorithm,
                    "tensor_backend": backend_name,
                },
            )
        ensure_paddlegan_vsr_weights(algorithm)
        return

    if backend_name != "onnx":
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"ONNX super-resolution does not support the '{backend_name}' tensor backend.",
            details={
                "stage": step.stage_name,
                "algorithm": algorithm,
                "tensor_backend": backend_name,
            },
        )
    model_name = step.algorithm_kwargs.get("onnx_model")
    _missing_onnx_model(
        step=step,
        backend_name=backend_name,
        algorithm=algorithm,
        kind="super_resolution",
        model_name=model_name if isinstance(model_name, str) else None,
    )


def validate_workflow_requirements(processing_steps: Sequence[ProcessingStep]) -> None:
    """Validate every executable stage against its own backend and model."""
    for step in processing_steps:
        if step.algorithm_type == "frame_interpolation":
            _validate_interpolation(step)
        elif step.algorithm_type == "super_resolution":
            _validate_super_resolution(step)


__all__ = ["validate_workflow_requirements"]
