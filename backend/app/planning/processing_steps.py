"""Typed processing-step contract shared by planning and streaming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AlgorithmType = Literal[
    "frame_interpolation",
    "super_resolution",
    "frame_filter_chain",
    "format_conversion",
]


@dataclass(frozen=True, slots=True)
class ProcessingStep:
    """One resolved algorithm stage in the backend pipeline."""

    algorithm_type: AlgorithmType
    algorithm_kwargs: dict[str, Any]
    stage_name: str

    def to_jsonable(self) -> dict[str, Any]:
        """Return the stable JSON shape used for signatures and sidecars."""
        return {
            "algorithm_type": self.algorithm_type,
            "algorithm_kwargs": dict(self.algorithm_kwargs),
            "stage_name": self.stage_name,
        }


__all__ = [
    "AlgorithmType",
    "ProcessingStep",
]
