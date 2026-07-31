"""Local filesystem adapter for model availability checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.errors import TaskErrorCode, raise_error
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

            ensure_paddlegan_vsr_weights(descriptor.factory_key)
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
