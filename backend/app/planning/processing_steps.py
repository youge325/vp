"""Typed processing-step contract shared by planning and streaming."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Mapping

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS

AlgorithmType = Literal[
    "frame_interpolation",
    "super_resolution",
    "frame_filter_chain",
]
StageExecutionMode = Literal["single", "pair", "sequence"]


@dataclass(frozen=True, slots=True)
class ProcessingStep:
    """One resolved algorithm stage in the backend pipeline."""

    algorithm_type: AlgorithmType
    algorithm_kwargs: Mapping[str, Any]
    stage_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "algorithm_kwargs", _freeze_mapping(self.algorithm_kwargs))

    @property
    def execution_mode(self) -> StageExecutionMode:
        """Declare the worker contract without probing an algorithm instance."""
        if self.algorithm_type == "frame_interpolation":
            return "pair"
        if (
            self.algorithm_type == "super_resolution"
            and str(self.algorithm_kwargs.get("sr_algorithm") or "") in PADDLEGAN_VSR_SPECS
        ):
            return "sequence"
        return "single"

    def to_jsonable(self) -> dict[str, Any]:
        """Return the stable JSON shape used for signatures and sidecars."""
        return {
            "algorithm_type": self.algorithm_type,
            "algorithm_kwargs": _thaw(self.algorithm_kwargs),
            "stage_name": self.stage_name,
        }


__all__ = [
    "AlgorithmType",
    "ProcessingStep",
]


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
