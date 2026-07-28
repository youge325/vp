"""Frame-filter chain orchestration shared by preprocessing and postprocessing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from app.algorithms.tensor_backend import ITensorBackend
from app.processing.frame_filter_handlers import (
    apply_numpy_filter,
    apply_tensor_filter,
    can_apply_tensor_filter,
    is_supported_filter_kind,
)


class FrameFilterChainAlgorithm:
    """Apply configured frame filters in order with tensor fallback when needed."""

    def __init__(self, tensor_backend: ITensorBackend | None = None, **kwargs: Any):
        self._tensor_backend = tensor_backend
        self._filters: Sequence[Mapping[str, Any]] = kwargs.get("filters") or ()
        self._validate_filters()

    def _validate_filters(self) -> None:
        for step in self._filters:
            if not isinstance(step, Mapping):
                raise ValueError("Filter step must be a mapping.")
            kind = step.get("kind")
            if not isinstance(kind, str) or not is_supported_filter_kind(kind):
                raise ValueError(f"Unknown filter kind: {kind}")
            if not isinstance(step.get("params"), Mapping):
                raise ValueError(f"Filter step '{kind}' missing params mapping.")

    def process_frame(self, frame: Any, **_kwargs: Any) -> Any:
        if self._tensor_backend is not None and self.can_process_tensor(self._tensor_backend):
            return self.process_tensor(frame, self._tensor_backend)
        if self._tensor_backend is None:
            return self.process_numpy(frame)
        numpy_frame = self._tensor_backend.tensor_to_numpy(frame)
        return self._tensor_backend.numpy_to_tensor(self.process_numpy(numpy_frame))

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        for step in self._filters:
            if step.get("enabled", True):
                frame = apply_numpy_filter(step["kind"], frame, step["params"])
        return frame

    def can_process_tensor(self, backend: ITensorBackend) -> bool:
        if backend.get_name().lower() != "pytorch":
            return False
        return all(
            not step.get("enabled", True) or can_apply_tensor_filter(step["kind"], step["params"])
            for step in self._filters
        )

    def process_tensor(self, tensor: Any, backend: ITensorBackend) -> Any:
        if not self.can_process_tensor(backend):
            raise RuntimeError("frame_filter_chain does not support tensor processing for this filter set.")
        for step in self._filters:
            if step.get("enabled", True):
                tensor = apply_tensor_filter(step["kind"], tensor, step["params"])
        return tensor
