"""Lazy implementation-key factory for the Real-RawVSR RGB catalog."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.algorithms.pytorch.real_rawvsr.fixed_window import RealRawVsrFixedWindow
from app.algorithms.pytorch.real_rawvsr.sequence_adapter import (
    ModelLoadSpec,
    build_model_load_spec,
)
from app.generated.model_assets import REAL_RAWVSR_MODEL_FAMILIES

type _ImplementationFactory = Callable[[ModelLoadSpec], Any]


def _load_basicvsr(spec: ModelLoadSpec, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr_basicvsr.network import load_basicvsr_model

    return load_basicvsr_model(spec, weight_path)


def _load_edvr(spec: ModelLoadSpec, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr.edvr import load_edvr_model

    return load_edvr_model(spec, weight_path)


def _load_tdan(spec: ModelLoadSpec, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr.tdan import load_tdan_model

    return load_tdan_model(spec, weight_path)


def _load_toflow(spec: ModelLoadSpec, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr.toflow import load_toflow_model

    return load_toflow_model(spec, weight_path)


def _create_basicvsr(spec: ModelLoadSpec) -> Any:
    from app.algorithms.pytorch.real_rawvsr_basicvsr.runner import RealRawVsrBasicVsr

    return RealRawVsrBasicVsr(spec=spec, model_loader=_load_basicvsr)


def _create_edvr(spec: ModelLoadSpec) -> Any:
    return RealRawVsrFixedWindow(spec=spec, model_loader=_load_edvr)


def _create_tdan(spec: ModelLoadSpec) -> Any:
    return RealRawVsrFixedWindow(spec=spec, model_loader=_load_tdan)


def _create_toflow(spec: ModelLoadSpec) -> Any:
    return RealRawVsrFixedWindow(spec=spec, model_loader=_load_toflow)


_IMPLEMENTATION_FACTORIES: dict[str, _ImplementationFactory] = {
    "basicvsr": _create_basicvsr,
    "edvr": _create_edvr,
    "tdan": _create_tdan,
    "toflow": _create_toflow,
}
_CATALOG_IMPLEMENTATIONS = {family.implementation_key for family in REAL_RAWVSR_MODEL_FAMILIES}
if set(_IMPLEMENTATION_FACTORIES) != _CATALOG_IMPLEMENTATIONS:
    raise RuntimeError("Real-RawVSR implementation factory and model-asset catalog differ.")


def create_real_rawvsr_algorithm(
    *,
    algorithm_id: str,
    scale_factor: int,
    num_frames: int,
    engine: str,
    model_root: str,
) -> Any:
    spec = build_model_load_spec(
        algorithm_id=algorithm_id,
        scale_factor=scale_factor,
        num_frames=num_frames,
        engine=engine,
        model_root=model_root,
    )
    return _IMPLEMENTATION_FACTORIES[spec.family.implementation_key](spec)


__all__ = ["create_real_rawvsr_algorithm"]
