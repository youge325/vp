"""Workflow validation helpers shared by CLI planning tests and commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings
from app.errors import TaskErrorCode, raise_error
from app.planning.processing_steps import ProcessingStep
from app.planning.workflow_steps import processing_needs_interpolation
from app.utils.onnx_models import resolve_onnx_model_path


def get_onnx_model_name(config: dict[str, Any]) -> str | None:
    return config.get("onnxModel") or config.get("onnx_model")


def _interpolation_model_path(model_version: str | None = None) -> Path:
    version = model_version or settings.RIFE_MODEL_VERSION
    return Path(settings.RIFE_MODEL_DIR) / f"flownet_v{version}.pkl"


def validate_onnx_models_for_workflow(
    workflow_config: dict[str, Any],
    processing_steps: list[ProcessingStep],
    tensor_backend_name: str,
) -> None:
    if tensor_backend_name != "onnx":
        return

    for step in processing_steps:
        if step.algorithm_type == "frame_interpolation":
            model_name = get_onnx_model_name(workflow_config["interpolation"])
            algorithm = workflow_config["interpolation"].get("algorithm", "rife")
            resolve_onnx_model_path("interpolation", algorithm, model_name, model_root=settings.RIFE_MODEL_DIR)
        elif step.algorithm_type == "super_resolution":
            model_name = get_onnx_model_name(workflow_config["superResolution"])
            algorithm = workflow_config["superResolution"].get("algorithm", "placeholder")
            resolve_onnx_model_path("super_resolution", algorithm, model_name, model_root=settings.RIFE_MODEL_DIR)


def verify_model_availability(
    workflow_config: dict[str, Any],
    processing_steps: list[ProcessingStep],
    tensor_backend_name: str,
) -> None:
    """Per-backend model existence guard."""
    from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS, ensure_paddlegan_vsr_weights

    for step in processing_steps:
        if step.algorithm_type != "super_resolution":
            continue
        sr_algorithm = str(step.algorithm_kwargs.get("sr_algorithm") or "")
        if sr_algorithm in PADDLEGAN_VSR_SPECS:
            super_resolution = workflow_config.get("superResolution", {})
            ensure_paddlegan_vsr_weights(
                sr_algorithm,
                auto_download=bool(
                    super_resolution.get("autoDownloadWeights")
                    or super_resolution.get("auto_download_weights")
                    or False
                ),
            )

    if processing_needs_interpolation(processing_steps):
        if tensor_backend_name == "onnx":
            try:
                validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name)
            except FileNotFoundError as exc:
                raise_error(
                    TaskErrorCode.MISSING_MODEL,
                    str(exc),
                    details={
                        "tensor_backend": tensor_backend_name,
                        "model_root": settings.RIFE_MODEL_DIR,
                    },
                )
        else:
            model_version = workflow_config["interpolation"]["model"]
            model_path = _interpolation_model_path(model_version)
            if not model_path.is_file() or model_path.stat().st_size == 0:
                raise_error(
                    TaskErrorCode.MISSING_MODEL,
                    f"Default interpolation model is missing: {model_path}",
                    details={
                        "model_path": str(model_path),
                        "model_version": model_version,
                    },
                )
    elif tensor_backend_name == "onnx":
        try:
            validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name)
        except FileNotFoundError as exc:
            raise_error(
                TaskErrorCode.MISSING_MODEL,
                str(exc),
                details={
                    "tensor_backend": tensor_backend_name,
                    "model_root": settings.RIFE_MODEL_DIR,
                },
            )


def verify_super_resolution_backend(
    workflow_config: dict[str, Any],
    tensor_backend_name: str,
) -> None:
    """Reject unsupported SR/backend combinations before execution."""
    super_resolution = workflow_config.get("superResolution", {})
    if not super_resolution.get("enabled"):
        return
    algorithm = str(super_resolution.get("algorithm") or "placeholder")
    sr_backend = str(
        super_resolution.get("tensorBackend") or super_resolution.get("tensor_backend") or tensor_backend_name
    )

    from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS

    if algorithm in PADDLEGAN_VSR_SPECS:
        scale_factor = float(super_resolution.get("scaleFactor") or super_resolution.get("scale_factor") or 1.0)
        if scale_factor != 4.0:
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"PaddleGAN VSR models are fixed 4x super-resolution models; got {scale_factor:g}x.",
                details={"algorithm": algorithm, "scale_factor": scale_factor},
            )
        if sr_backend != "paddle":
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"PaddleGAN VSR requires the Paddle tensor backend; got '{sr_backend}'.",
                details={"algorithm": algorithm, "tensor_backend": sr_backend},
            )
        interpolation = workflow_config.get("interpolation", {})
        interpolation_backend = str(
            interpolation.get("tensorBackend") or interpolation.get("tensor_backend") or tensor_backend_name
        )
        if interpolation.get("enabled") and interpolation_backend == "paddle":
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                (
                    "RIFE interpolation does not support the Paddle tensor backend. "
                    "Use PyTorch or ONNX for interpolation when combining it with PaddleGAN VSR."
                ),
                details={
                    "super_resolution_backend": "paddle",
                    "interpolation_backend": interpolation_backend,
                },
            )
        return

    if sr_backend == "onnx":
        return
    raise_error(
        TaskErrorCode.INVALID_CONFIG,
        (
            "Super-resolution requires the ONNX tensor backend; "
            f"got '{sr_backend}'. Switch the tensor backend to onnx "
            "or disable super-resolution."
        ),
        details={
            "tensor_backend": sr_backend,
            "super_resolution_enabled": True,
        },
    )


__all__ = [
    "get_onnx_model_name",
    "validate_onnx_models_for_workflow",
    "verify_model_availability",
    "verify_super_resolution_backend",
]
