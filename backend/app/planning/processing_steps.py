"""Typed processing-step contract shared by planning and streaming.

The Rust / frontend wire payload still carries plain JSON objects. Once the
Python backend has validated that payload, internal code should pass explicit
``ProcessingStep`` instances instead of relying on repeated string-key access.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, cast

AlgorithmType = Literal[
    "frame_interpolation",
    "super_resolution",
    "frame_filter_chain",
    "format_conversion",
]

_KNOWN_ALGORITHM_TYPES: set[str] = {
    "frame_interpolation",
    "super_resolution",
    "frame_filter_chain",
    "format_conversion",
}


@dataclass(frozen=True, slots=True)
class ProcessingStep:
    """One resolved algorithm stage in the backend pipeline."""

    algorithm_type: AlgorithmType
    algorithm_kwargs: dict[str, Any] = field(default_factory=dict)
    stage_name: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        """Return the legacy JSON shape used for signatures and sidecars."""
        return {
            "algorithm_type": self.algorithm_type,
            "algorithm_kwargs": dict(self.algorithm_kwargs),
            "stage_name": self.stage_name,
        }


ProcessingStepInput: TypeAlias = ProcessingStep | Mapping[str, Any]


def normalize_processing_step(step: ProcessingStepInput) -> ProcessingStep:
    """Accept a typed step or legacy mapping and return ``ProcessingStep``."""
    if isinstance(step, ProcessingStep):
        return step
    if not isinstance(step, Mapping):
        raise TypeError(f"Processing step must be a mapping or ProcessingStep, got {type(step).__name__}.")

    algorithm_type = step.get("algorithm_type")
    if not isinstance(algorithm_type, str) or algorithm_type not in _KNOWN_ALGORITHM_TYPES:
        raise ValueError(f"Unknown processing step algorithm_type: {algorithm_type!r}")

    algorithm_kwargs = step.get("algorithm_kwargs", {})
    if algorithm_kwargs is None:
        algorithm_kwargs = {}
    if not isinstance(algorithm_kwargs, Mapping):
        raise TypeError("Processing step algorithm_kwargs must be a mapping.")

    stage_name = step.get("stage_name")
    if not isinstance(stage_name, str) or not stage_name:
        raise ValueError("Processing step stage_name must be a non-empty string.")

    return ProcessingStep(
        algorithm_type=cast(AlgorithmType, algorithm_type),
        algorithm_kwargs=dict(algorithm_kwargs),
        stage_name=stage_name,
    )


def normalize_processing_steps(steps: Iterable[ProcessingStepInput]) -> list[ProcessingStep]:
    """Normalize a processing-step iterable while preserving order."""
    return [normalize_processing_step(step) for step in steps]


def processing_steps_to_jsonable(steps: Iterable[ProcessingStepInput]) -> list[dict[str, Any]]:
    """Serialize processing steps to the legacy dict shape."""
    return [normalize_processing_step(step).to_jsonable() for step in steps]


__all__ = [
    "AlgorithmType",
    "ProcessingStep",
    "ProcessingStepInput",
    "normalize_processing_step",
    "normalize_processing_steps",
    "processing_steps_to_jsonable",
]
