"""Local filesystem adapter for model availability checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.errors.codes import TaskErrorCode
from app.errors.process import raise_error
from app.planning.processing_steps import ProcessingStep
from app.utils.onnx_models import resolve_onnx_model_path


@dataclass(frozen=True, slots=True)
class LocalModelAvailability:
    model_root: str

    def validate(self, step: ProcessingStep) -> None:
        descriptor = step.descriptor
        backend_name = str(step.algorithm_kwargs["tensor_backend"])
        if descriptor.model_kind == "paddlegan_vsr":
            from app.algorithms.paddle.paddlegan_vsr.weights import ensure_paddlegan_vsr_weights

            ensure_paddlegan_vsr_weights(str(step.algorithm_kwargs["sr_algorithm"]))
            return
        if descriptor.model_kind == "pytorch_vsr":
            from app.algorithms.pytorch.real_rawvsr.assets import ensure_model_asset, family_for_algorithm

            algorithm = str(step.algorithm_kwargs["sr_algorithm"])
            family = family_for_algorithm(algorithm)
            scale_factor = int(step.algorithm_kwargs["scale_factor"])
            try:
                model_path = ensure_model_asset(self.model_root, algorithm, scale_factor)
            except (FileNotFoundError, RuntimeError, ValueError) as exc:
                raise_error(
                    TaskErrorCode.MISSING_MODEL,
                    str(exc),
                    details={
                        "stage": step.stage_name,
                        "algorithm": algorithm,
                        "scale_factor": scale_factor,
                    },
                )
            try:
                import torch
            except ImportError:
                raise_error(
                    TaskErrorCode.MISSING_TENSOR_BACKEND,
                    f"{family.display_name} x{scale_factor} requires PyTorch with NVIDIA CUDA support.",
                    details={"stage": step.stage_name, "algorithm": algorithm, "model_path": str(model_path)},
                )
            if not torch.cuda.is_available():
                raise_error(
                    TaskErrorCode.MISSING_TENSOR_BACKEND,
                    f"{family.display_name} x{scale_factor} requires an available NVIDIA CUDA device.",
                    details={"stage": step.stage_name, "algorithm": algorithm, "model_path": str(model_path)},
                )
            if algorithm in {"real-rawvsr-edvr", "real-rawvsr-tdan"}:
                try:
                    from torchvision.ops import deform_conv2d
                except (ImportError, RuntimeError) as exc:
                    raise_error(
                        TaskErrorCode.MISSING_TENSOR_BACKEND,
                        f"{family.display_name} x{scale_factor} requires torchvision CUDA deform_conv2d: {exc}",
                        details={"stage": step.stage_name, "algorithm": algorithm, "model_path": str(model_path)},
                    )
                if not callable(deform_conv2d):  # pragma: no cover - defensive dependency guard
                    raise_error(
                        TaskErrorCode.MISSING_TENSOR_BACKEND,
                        f"{family.display_name} x{scale_factor} requires torchvision CUDA deform_conv2d.",
                        details={"stage": step.stage_name, "algorithm": algorithm, "model_path": str(model_path)},
                    )
            return
        if descriptor.model_kind == "rife" and backend_name == "pytorch":
            model_version = str(step.algorithm_kwargs["model_version"])
            model_path = Path(self.model_root) / f"flownet_v{model_version}.pkl"
            if not model_path.is_file() or model_path.stat().st_size == 0:
                raise_error(
                    TaskErrorCode.MISSING_MODEL,
                    f"Interpolation model is missing: {model_path}",
                    details={
                        "stage": step.stage_name,
                        "algorithm": "rife",
                        "tensor_backend": backend_name,
                        "model_path": str(model_path),
                        "model_version": model_version,
                    },
                )
            return
        if backend_name == "onnx":
            kind = "interpolation" if descriptor.model_kind == "rife" else "super_resolution"
            algorithm_key = "algorithm" if descriptor.model_kind == "rife" else "sr_algorithm"
            algorithm = str(step.algorithm_kwargs[algorithm_key])
            model_name = step.algorithm_kwargs.get("onnx_model")
            try:
                resolve_onnx_model_path(
                    kind,
                    algorithm,
                    model_name if isinstance(model_name, str) else None,
                    model_root=self.model_root,
                )
            except FileNotFoundError as exc:
                raise_error(
                    TaskErrorCode.MISSING_MODEL,
                    str(exc),
                    details={
                        "stage": step.stage_name,
                        "algorithm": algorithm,
                        "tensor_backend": backend_name,
                        "model_root": self.model_root,
                    },
                )


__all__ = ["LocalModelAvailability"]
