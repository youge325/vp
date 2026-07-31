"""Neutral stage metadata shared by planning, execution, and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from app.catalog.filter_geometry import project_filter_chain

AlgorithmType = Literal["frame_interpolation", "super_resolution", "frame_filter_chain"]
StageExecutionMode = Literal["single", "pair", "sequence"]
StageModelKind = Literal["rife", "onnx_super_resolution", "paddlegan_vsr", "filter_chain"]
GeometryKind = Literal["preserve", "configured_scale", "fixed_scale", "filter_chain"]


@dataclass(frozen=True, slots=True)
class _GeometryPolicy:
    """Pure dimension projection owned by the stage descriptor."""

    kind: GeometryKind
    fixed_scale_factor: float | None = None

    def project(
        self,
        *,
        input_width: int,
        input_height: int,
        algorithm_kwargs: Mapping[str, Any],
    ) -> tuple[int, int]:
        width = int(input_width)
        height = int(input_height)
        if self.kind == "preserve":
            return width, height
        if self.kind in {"configured_scale", "fixed_scale"}:
            scale = self.fixed_scale_factor
            if scale is None:
                scale = float(algorithm_kwargs["scale_factor"])
            return max(1, round(width * scale)), max(1, round(height * scale))
        return project_filter_chain(width, height, algorithm_kwargs.get("filters", ()))


@dataclass(frozen=True, slots=True)
class StageDescriptor:
    """Immutable capabilities for one resolved processing stage."""

    execution_mode: StageExecutionMode
    requires_file_pipeline: bool
    geometry: _GeometryPolicy
    supported_backends: frozenset[str]
    factory_key: str
    model_kind: StageModelKind

    @property
    def fixed_scale_factor(self) -> float | None:
        """Expose the scale projection without storing duplicate metadata."""
        return self.geometry.fixed_scale_factor


RIFE_STAGE_DESCRIPTOR = StageDescriptor(
    execution_mode="pair",
    requires_file_pipeline=True,
    geometry=_GeometryPolicy("preserve"),
    supported_backends=frozenset({"pytorch", "onnx"}),
    factory_key="rife",
    model_kind="rife",
)

ONNX_SUPER_RESOLUTION_DESCRIPTOR = StageDescriptor(
    execution_mode="single",
    requires_file_pipeline=False,
    geometry=_GeometryPolicy("configured_scale"),
    supported_backends=frozenset({"onnx"}),
    factory_key="onnx_super_resolution",
    model_kind="onnx_super_resolution",
)

FILTER_CHAIN_DESCRIPTOR = StageDescriptor(
    execution_mode="single",
    requires_file_pipeline=False,
    geometry=_GeometryPolicy("filter_chain"),
    supported_backends=frozenset(),
    factory_key="filter_chain",
    model_kind="filter_chain",
)

PADDLEGAN_STAGE_DESCRIPTOR = StageDescriptor(
    execution_mode="sequence",
    requires_file_pipeline=True,
    geometry=_GeometryPolicy("fixed_scale", fixed_scale_factor=4.0),
    supported_backends=frozenset({"paddle"}),
    factory_key="paddlegan_vsr",
    model_kind="paddlegan_vsr",
)


__all__ = [
    "AlgorithmType",
    "FILTER_CHAIN_DESCRIPTOR",
    "ONNX_SUPER_RESOLUTION_DESCRIPTOR",
    "PADDLEGAN_STAGE_DESCRIPTOR",
    "RIFE_STAGE_DESCRIPTOR",
    "StageDescriptor",
    "StageExecutionMode",
]
