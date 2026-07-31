"""Neutral stage metadata shared by planning, execution, and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS

AlgorithmType = Literal["frame_interpolation", "super_resolution", "frame_filter_chain"]
StageExecutionMode = Literal["single", "pair", "sequence"]
StageModelKind = Literal["rife", "onnx_super_resolution", "paddlegan_vsr", "filter_chain"]


@dataclass(frozen=True, slots=True)
class StageDescriptor:
    """Immutable capabilities for one resolved processing stage."""

    execution_mode: StageExecutionMode
    requires_file_pipeline: bool
    changes_dimensions: bool
    supported_backends: frozenset[str]
    fixed_scale_factor: float | None
    factory_key: str
    model_kind: StageModelKind


RIFE_STAGE_DESCRIPTOR = StageDescriptor(
    execution_mode="pair",
    requires_file_pipeline=True,
    changes_dimensions=False,
    supported_backends=frozenset({"pytorch", "onnx"}),
    fixed_scale_factor=None,
    factory_key="rife",
    model_kind="rife",
)

ONNX_SUPER_RESOLUTION_DESCRIPTOR = StageDescriptor(
    execution_mode="single",
    requires_file_pipeline=False,
    changes_dimensions=True,
    supported_backends=frozenset({"onnx"}),
    fixed_scale_factor=None,
    factory_key="onnx_super_resolution",
    model_kind="onnx_super_resolution",
)

FILTER_CHAIN_DESCRIPTOR = StageDescriptor(
    execution_mode="single",
    requires_file_pipeline=False,
    changes_dimensions=False,
    supported_backends=frozenset(),
    fixed_scale_factor=None,
    factory_key="filter_chain",
    model_kind="filter_chain",
)

PADDLEGAN_STAGE_DESCRIPTORS: dict[str, StageDescriptor] = {
    model_id: StageDescriptor(
        execution_mode="sequence",
        requires_file_pipeline=True,
        changes_dimensions=True,
        supported_backends=frozenset({"paddle"}),
        fixed_scale_factor=4.0,
        factory_key=model_id,
        model_kind="paddlegan_vsr",
    )
    for model_id in PADDLEGAN_VSR_SPECS
}


def resolve_stage_descriptor(
    algorithm_type: AlgorithmType,
    algorithm_kwargs: Mapping[str, Any],
) -> StageDescriptor:
    """Resolve stage capabilities without importing an algorithm implementation."""
    if algorithm_type == "frame_interpolation":
        return RIFE_STAGE_DESCRIPTOR
    if algorithm_type == "super_resolution":
        algorithm = str(algorithm_kwargs.get("sr_algorithm") or "")
        return PADDLEGAN_STAGE_DESCRIPTORS.get(algorithm, ONNX_SUPER_RESOLUTION_DESCRIPTOR)
    return FILTER_CHAIN_DESCRIPTOR


__all__ = [
    "AlgorithmType",
    "PADDLEGAN_STAGE_DESCRIPTORS",
    "StageDescriptor",
    "StageExecutionMode",
    "resolve_stage_descriptor",
]
