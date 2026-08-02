"""Shared lifecycle and error boundary for Real-RawVSR sequence adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.algorithms.pytorch.real_rawvsr.assets import (
    ensure_model_asset,
    family_for_algorithm,
    variant_for_algorithm_scale,
)
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError

type ModelLoader = Callable[[int, str], tuple[Any, Any]]


class RealRawVsrSequenceAdapter(ABC):
    def __init__(self, *, algorithm_id: str, scale_factor: int, engine: str, model_root: str) -> None:
        family = family_for_algorithm(algorithm_id)
        variant_for_algorithm_scale(algorithm_id, scale_factor)
        if engine != "cuda":
            raise ValueError(f"{family.display_name} supports only CUDA; got {engine!r}.")
        self._family = family
        self._algorithm_id = algorithm_id
        self._scale_factor = scale_factor
        self._model_root = model_root
        self._torch: Any | None = None
        self._model: Any | None = None

    def _load_model(self, loader: ModelLoader) -> tuple[Any, Any]:
        if self._torch is None or self._model is None:
            model_path = ensure_model_asset(self._model_root, self._algorithm_id, self._scale_factor)
            self._torch, self._model = loader(self._scale_factor, str(model_path))
        return self._torch, self._model

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

    @abstractmethod
    def process_frames(
        self,
        frames: Sequence[np.ndarray],
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]: ...


__all__ = ["ModelLoader", "RealRawVsrSequenceAdapter"]
