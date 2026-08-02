"""Single immutable catalog for algorithm discovery and stage resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from app.catalog.rife_models import SUPPORTED_MODELS
from app.catalog.stage_descriptors import (
    AlgorithmType,
    FILTER_CHAIN_DESCRIPTOR,
    ONNX_SUPER_RESOLUTION_DESCRIPTOR,
    PADDLEGAN_STAGE_DESCRIPTOR,
    REAL_RAWVSR_RGB_STAGE_DESCRIPTOR,
    RIFE_STAGE_DESCRIPTOR,
    StageDescriptor,
)
from app.generated.model_assets import (
    REAL_RAWVSR_LICENSE_SPDX,
    REAL_RAWVSR_LICENSE_USAGE,
    REAL_RAWVSR_MODEL_FAMILIES,
    REAL_RAWVSR_SOURCE_URL,
)

InputFrameModeName = Literal["none", "editable_chunk", "fixed_window"]


@dataclass(frozen=True, slots=True)
class _ModelLicenseCapability:
    spdx_id: str
    usage: Literal["non_commercial"]
    source_url: str


@dataclass(frozen=True, slots=True)
class AlgorithmCapability:
    """Discovery metadata and execution descriptor for one public algorithm."""

    name: str
    descriptor: StageDescriptor
    models: tuple[str, ...]
    input_frame_mode: InputFrameModeName
    default_num_frames: int | None = None
    scale_factors: tuple[int, ...] = ()
    model_license: _ModelLicenseCapability | None = None


RIFE_CAPABILITY = AlgorithmCapability(
    name="rife",
    descriptor=RIFE_STAGE_DESCRIPTOR,
    models=tuple(SUPPORTED_MODELS),
    input_frame_mode="none",
)

ONNX_SUPER_RESOLUTION_CAPABILITY = AlgorithmCapability(
    name="placeholder",
    descriptor=ONNX_SUPER_RESOLUTION_DESCRIPTOR,
    models=(),
    input_frame_mode="none",
)

_PADDLEGAN_CAPABILITIES = tuple(
    AlgorithmCapability(
        name=model_id,
        descriptor=PADDLEGAN_STAGE_DESCRIPTOR,
        models=("x4",),
        input_frame_mode="fixed_window" if spec.sequence_mode == "window" else "editable_chunk",
        default_num_frames=spec.default_num_frames,
        scale_factors=(4,),
    )
    for model_id, spec in PADDLEGAN_VSR_SPECS.items()
)

_REAL_RAWVSR_CAPABILITIES = tuple(
    AlgorithmCapability(
        name=family.algorithm_id,
        descriptor=REAL_RAWVSR_RGB_STAGE_DESCRIPTOR,
        models=tuple(f"x{variant.scale_factor}" for variant in family.variants),
        input_frame_mode=family.input_frame_mode,
        default_num_frames=family.default_num_frames,
        scale_factors=tuple(variant.scale_factor for variant in family.variants),
        model_license=_ModelLicenseCapability(
            spdx_id=REAL_RAWVSR_LICENSE_SPDX,
            usage=REAL_RAWVSR_LICENSE_USAGE,
            source_url=REAL_RAWVSR_SOURCE_URL,
        ),
    )
    for family in REAL_RAWVSR_MODEL_FAMILIES
)

INTERPOLATION_CAPABILITIES = (RIFE_CAPABILITY,)
SUPER_RESOLUTION_CAPABILITIES = (
    ONNX_SUPER_RESOLUTION_CAPABILITY,
    *_REAL_RAWVSR_CAPABILITIES,
    *_PADDLEGAN_CAPABILITIES,
)
_CAPABILITIES_BY_TYPE = {
    "frame_interpolation": {capability.name: capability for capability in INTERPOLATION_CAPABILITIES},
    "super_resolution": {capability.name: capability for capability in SUPER_RESOLUTION_CAPABILITIES},
}


def project_dynamic_onnx_super_resolution_capabilities(
    discovered_algorithms: Mapping[str, object],
) -> tuple[AlgorithmCapability, ...]:
    """Expose discovered ONNX routes without colliding with static algorithms."""
    reserved_names = {capability.name for capability in SUPER_RESOLUTION_CAPABILITIES}
    return tuple(
        AlgorithmCapability(
            name=name,
            descriptor=ONNX_SUPER_RESOLUTION_DESCRIPTOR,
            models=(),
            input_frame_mode="none",
        )
        for name in sorted(discovered_algorithms, key=str.casefold)
        if name not in reserved_names
    )


def find_static_algorithm_capability(
    algorithm_type: AlgorithmType,
    name: str,
) -> AlgorithmCapability | None:
    return _CAPABILITIES_BY_TYPE.get(algorithm_type, {}).get(name)


def resolve_stage_descriptor(
    algorithm_type: AlgorithmType,
    algorithm_kwargs: Mapping[str, Any],
) -> StageDescriptor:
    """Resolve capabilities without importing an algorithm implementation."""
    if algorithm_type == "frame_filter_chain":
        return FILTER_CHAIN_DESCRIPTOR
    if algorithm_type == "frame_interpolation":
        return RIFE_STAGE_DESCRIPTOR
    if algorithm_type != "super_resolution":
        raise ValueError(f"Unknown processing stage type: {algorithm_type!r}")
    name = algorithm_kwargs.get("sr_algorithm")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Super-resolution processing requires an explicit sr_algorithm.")
    capability = _CAPABILITIES_BY_TYPE[algorithm_type].get(name)
    if capability is None:
        # ONNX algorithms are discovered dynamically from model directories;
        # ``placeholder`` is the built-in route, not an exhaustive name list.
        return ONNX_SUPER_RESOLUTION_DESCRIPTOR
    return capability.descriptor


__all__ = [
    "AlgorithmCapability",
    "INTERPOLATION_CAPABILITIES",
    "SUPER_RESOLUTION_CAPABILITIES",
    "project_dynamic_onnx_super_resolution_capabilities",
    "find_static_algorithm_capability",
    "resolve_stage_descriptor",
]
