"""Shared lifecycle, immutable load policy, and error boundary for RGB VSR."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.algorithms.pytorch.real_rawvsr.assets import (
    ensure_model_asset,
    family_for_algorithm,
    variant_for_algorithm_scale,
)
from app.algorithms.pytorch.real_rawvsr.rgb_frames import RgbTensorCodec
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from app.generated.model_assets import REAL_RAWVSR_ENGINES, ModelAssetFamily, ModelAssetVariant


@dataclass(frozen=True, slots=True)
class ModelLoadSpec:
    """All model-selection and input-policy facts required by an implementation."""

    family: ModelAssetFamily
    variant: ModelAssetVariant
    num_frames: int
    model_root: str

    @property
    def algorithm_id(self) -> str:
        return self.family.algorithm_id

    @property
    def scale_factor(self) -> int:
        return self.variant.scale_factor


type ModelLoader = Callable[[ModelLoadSpec, str], tuple[Any, Any]]


def build_model_load_spec(
    *,
    algorithm_id: str,
    scale_factor: int,
    num_frames: int,
    engine: str,
    model_root: str,
) -> ModelLoadSpec:
    """Resolve and validate a request against the generated asset policy once."""

    family = family_for_algorithm(algorithm_id)
    variant = variant_for_algorithm_scale(algorithm_id, scale_factor)
    if engine not in REAL_RAWVSR_ENGINES:
        supported = ", ".join(value.upper() for value in REAL_RAWVSR_ENGINES)
        raise ValueError(f"{family.display_name} supports only {supported}; got {engine!r}.")
    if num_frames < 1:
        raise ValueError(f"{family.display_name} num_frames must be at least 1.")
    if family.input_frame_mode == "fixed_window" and num_frames != family.default_num_frames:
        raise ValueError(f"{family.display_name} requires exactly {family.default_num_frames} frames per window.")
    return ModelLoadSpec(
        family=family,
        variant=variant,
        num_frames=num_frames,
        model_root=model_root,
    )


class RealRawVsrSequenceAdapter(ABC):
    def __init__(self, spec: ModelLoadSpec, model_loader: ModelLoader) -> None:
        self._spec = spec
        self._family = spec.family
        self._algorithm_id = spec.algorithm_id
        self._scale_factor = spec.scale_factor
        self._codec = RgbTensorCodec(
            display_name=spec.family.display_name,
            minimum_size=spec.family.spatial_policy.minimum_size,
            size_multiple=spec.family.spatial_policy.size_multiple,
            scale_factor=spec.scale_factor,
        )
        self._model_loader = model_loader
        self._torch: Any | None = None
        self._model: Any | None = None

    def _load_model(self) -> tuple[Any, Any]:
        if self._torch is None or self._model is None:
            model_path = ensure_model_asset(
                self._spec.model_root,
                self._spec.algorithm_id,
                self._spec.scale_factor,
            )
            self._torch, self._model = self._model_loader(self._spec, str(model_path))
        return self._torch, self._model

    def _prepare_runtime(self, frames: Sequence[np.ndarray]) -> tuple[Any, Any] | None:
        prepared = self._codec.prepare(frames)
        if prepared is None:
            return None
        torch, _model = self._load_model()
        return prepared, torch

    def _run_model(self, tensor: Any, *, oom_message: str, details: dict[str, Any]) -> Any:
        torch, model = self._torch, self._model
        if torch is None or model is None:
            raise RuntimeError("Real-RawVSR model must be loaded before inference.")
        try:
            with torch.inference_mode():
                return model(tensor)
        except torch.cuda.OutOfMemoryError as exc:
            torch.cuda.empty_cache()
            raise ProcessError(TaskErrorCode.PROCESS_FAILED, oom_message, details=details) from exc

    def process_frame_sequence(
        self,
        frames: list[Any],
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[Any]:
        return self.process_frames(frames, progress_callback=progress_callback)

    def process_frames(
        self,
        frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        runtime = self._prepare_runtime(frames)
        if runtime is None:
            return []
        prepared, torch = runtime
        return self._process_prepared(prepared, torch, progress_callback=progress_callback)

    @abstractmethod
    def _process_prepared(
        self,
        prepared: Any,
        torch: Any,
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[np.ndarray]: ...


__all__ = ["ModelLoadSpec", "ModelLoader", "RealRawVsrSequenceAdapter", "build_model_load_spec"]
