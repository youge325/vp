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
class _ResolvedModelAsset:
    family: ModelAssetFamily
    variant: ModelAssetVariant


@dataclass(frozen=True, slots=True)
class ModelLoadSpec:
    """Runtime inputs plus one resolved catalog-owned model selection."""

    asset: _ResolvedModelAsset
    num_frames: int
    model_root: str


type ModelLoader = Callable[[ModelLoadSpec, str], tuple[Any, Any]]


@dataclass(frozen=True, slots=True)
class LoadedModelRuntime:
    """Atomic owner for the framework and its loaded inference model."""

    torch: Any
    model: Any


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
        asset=_ResolvedModelAsset(family=family, variant=variant),
        num_frames=num_frames,
        model_root=model_root,
    )


class RealRawVsrSequenceAdapter(ABC):
    def __init__(self, spec: ModelLoadSpec, model_loader: ModelLoader) -> None:
        self._spec = spec
        family = spec.asset.family
        variant = spec.asset.variant
        self._codec = RgbTensorCodec(
            display_name=family.display_name,
            minimum_size=family.spatial_policy.minimum_size,
            size_multiple=family.spatial_policy.size_multiple,
            scale_factor=variant.scale_factor,
        )
        self._model_loader = model_loader
        self._loaded_runtime: LoadedModelRuntime | None = None

    def _load_model(self) -> LoadedModelRuntime:
        if self._loaded_runtime is None:
            model_path = ensure_model_asset(
                self._spec.model_root,
                self._spec.asset.family.algorithm_id,
                self._spec.asset.variant.scale_factor,
            )
            torch, model = self._model_loader(self._spec, str(model_path))
            self._loaded_runtime = LoadedModelRuntime(torch=torch, model=model)
        return self._loaded_runtime

    def _prepare_runtime(self, frames: Sequence[np.ndarray]) -> tuple[Any, LoadedModelRuntime] | None:
        prepared = self._codec.prepare(frames)
        if prepared is None:
            return None
        return prepared, self._load_model()

    @staticmethod
    def _run_model(
        runtime: LoadedModelRuntime,
        tensor: Any,
        *,
        oom_message: str,
        details: dict[str, Any],
    ) -> Any:
        try:
            with runtime.torch.inference_mode():
                return runtime.model(tensor)
        except runtime.torch.cuda.OutOfMemoryError as exc:
            runtime.torch.cuda.empty_cache()
            raise ProcessError(TaskErrorCode.PROCESS_FAILED, oom_message, details=details) from exc

    def process_frame_sequence(
        self,
        frames: list[Any],
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[Any]:
        runtime = self._prepare_runtime(frames)
        if runtime is None:
            return []
        prepared, loaded_runtime = runtime
        return self._process_prepared(prepared, loaded_runtime, progress_callback=progress_callback)

    @abstractmethod
    def _process_prepared(
        self,
        prepared: Any,
        runtime: LoadedModelRuntime,
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[np.ndarray]: ...


__all__ = [
    "LoadedModelRuntime",
    "ModelLoadSpec",
    "ModelLoader",
    "RealRawVsrSequenceAdapter",
    "build_model_load_spec",
]
