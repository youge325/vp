"""Internal frame carrier with lazy numpy/tensor conversion.

``FramePayload`` keeps the streaming processor honest about host/device
transfers: callers ask for the representation they need, and the payload
converts at most once per cached representation.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from app.processing.streaming.metrics import PipelineMetrics


@dataclass(slots=True)
class FramePayload:
    """A single frame represented as either numpy, tensor, or both."""

    _numpy_frame: np.ndarray | None = None
    _tensor: Any | None = None
    _tensor_backend: Any | None = None

    @classmethod
    def from_numpy(cls, frame: np.ndarray) -> "FramePayload":
        return cls(_numpy_frame=frame)

    @classmethod
    def from_tensor(cls, tensor: Any, backend: Any) -> "FramePayload":
        return cls(_tensor=tensor, _tensor_backend=backend)

    def ensure_tensor(self, backend: Any, metrics: PipelineMetrics | None = None) -> Any:
        """Return the backend tensor, uploading from numpy lazily if needed."""
        if self._tensor is not None:
            self._ensure_backend_matches(backend)
            return self._tensor
        if self._numpy_frame is None:
            raise RuntimeError("FramePayload has neither tensor nor numpy data.")

        started_at = time.perf_counter()
        self._tensor = backend.numpy_to_tensor(self._numpy_frame)
        elapsed = time.perf_counter() - started_at
        self._tensor_backend = backend
        if metrics is not None:
            metrics.record_transfer("h2d", seconds=elapsed)
        return self._tensor

    def ensure_numpy(self, metrics: PipelineMetrics | None = None) -> np.ndarray:
        """Return a numpy frame, downloading from tensor lazily if needed."""
        if self._numpy_frame is not None:
            return self._numpy_frame
        if self._tensor is None or self._tensor_backend is None:
            raise RuntimeError("FramePayload has neither numpy data nor a tensor backend.")

        started_at = time.perf_counter()
        self._numpy_frame = self._tensor_backend.tensor_to_numpy(self._tensor)
        elapsed = time.perf_counter() - started_at
        if metrics is not None:
            metrics.record_transfer("d2h", seconds=elapsed)
        return self._numpy_frame

    def has_tensor_for(self, backend: Any) -> bool:
        """Return whether a tensor for *backend* is already cached."""
        if self._tensor is None:
            return False
        self._ensure_backend_matches(backend)
        return True

    def _ensure_backend_matches(self, backend: Any) -> None:
        if self._tensor_backend is backend:
            return
        raise RuntimeError(
            "FramePayload tensor backend mismatch: cached tensor belongs to "
            f"{_backend_label(self._tensor_backend)}, requested {_backend_label(backend)}."
        )


def _backend_label(backend: Any) -> str:
    if backend is None:
        return "<none>"
    get_name = getattr(backend, "get_name", None)
    if callable(get_name):
        try:
            return str(get_name())
        except Exception:
            pass
    return type(backend).__name__


__all__ = ["FramePayload"]
