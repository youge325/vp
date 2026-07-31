"""Frame-filter chain orchestration shared by preprocessing and postprocessing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from app.catalog.filter_geometry import validate_filter_geometry
from app.processing.frame_filter_handlers import (
    apply_numpy_filter,
    is_supported_filter_kind,
)


class FrameFilterChainAlgorithm:
    """Apply configured frame filters in order on CPU frames."""

    def __init__(self, *, filters: Sequence[Mapping[str, Any]]) -> None:
        self._filters = filters
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
            validate_filter_geometry(kind, step["params"])

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        for step in self._filters:
            if step.get("enabled", True):
                frame = apply_numpy_filter(step["kind"], frame, step["params"])
        return frame
