"""Frame-filter chain orchestration shared by preprocessing and postprocessing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.catalog.filter_parameters import FilterParams, normalize_filter_params
from app.processing.frame_filter_handlers import (
    apply_numpy_filter,
    is_supported_filter_kind,
)


@dataclass(frozen=True, slots=True)
class _ConfiguredFilter:
    kind: str
    enabled: bool
    params: FilterParams


class FrameFilterChainAlgorithm:
    """Apply configured frame filters in order on CPU frames."""

    def __init__(self, *, filters: Sequence[Mapping[str, Any]]) -> None:
        self._filters = self._normalize_filters(filters)

    @staticmethod
    def _normalize_filters(filters: Sequence[Mapping[str, Any]]) -> tuple[_ConfiguredFilter, ...]:
        normalized: list[_ConfiguredFilter] = []
        for step in filters:
            if not isinstance(step, Mapping):
                raise ValueError("Filter step must be a mapping.")
            kind = step.get("kind")
            if not isinstance(kind, str) or not is_supported_filter_kind(kind):
                raise ValueError(f"Unknown filter kind: {kind}")
            if not isinstance(step.get("params"), Mapping):
                raise ValueError(f"Filter step '{kind}' missing params mapping.")
            normalized.append(
                _ConfiguredFilter(
                    kind=kind,
                    enabled=bool(step.get("enabled", True)),
                    params=normalize_filter_params(kind, step["params"]),
                )
            )
        return tuple(normalized)

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        for step in self._filters:
            if step.enabled:
                frame = apply_numpy_filter(step.kind, frame, step.params)
        return frame
