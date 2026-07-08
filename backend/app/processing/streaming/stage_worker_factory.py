"""Algorithm and backend factories for isolated stage workers."""

from __future__ import annotations

from typing import Any, Callable

from app.algorithms.factory import AlgorithmFactory
from app.planning import ProcessingStep
from app.processing.streaming.stage_rules import algorithm_kwargs_for_create

AlgorithmFactoryFn = Callable[[ProcessingStep, Any], Any]
BackendFactoryFn = Callable[[str], Any]


def create_backend(config: Any, backend_factory: BackendFactoryFn) -> Any:
    if config.stage.algorithm_type == "frame_filter_chain":
        return None
    return backend_factory(config.tensor_backend_name)


def create_algorithm(stage: ProcessingStep, backend: Any) -> Any:
    if stage.algorithm_type == "frame_filter_chain":
        from app.processing.frame_filters import FrameFilterChainAlgorithm

        return FrameFilterChainAlgorithm(tensor_backend=None, **stage.algorithm_kwargs)

    register_single_algorithm(stage.algorithm_type)
    return AlgorithmFactory.create(
        algorithm_type=stage.algorithm_type,
        tensor_backend=backend,
        tensor_backend_name=backend_name(backend),
        **algorithm_kwargs_for_create(stage),
    )


def register_single_algorithm(algorithm_type: str) -> None:
    if algorithm_type == "frame_interpolation":
        from app.processing.interpolation import FrameInterpolationAlgorithm

        AlgorithmFactory.register("frame_interpolation", FrameInterpolationAlgorithm)
        return
    if algorithm_type == "super_resolution":
        from app.processing.super_resolution import SuperResolutionAlgorithm

        AlgorithmFactory.register("super_resolution", SuperResolutionAlgorithm)
        return
    if algorithm_type == "anime_optimization":
        from app.processing.anime_optimization import AnimeOptimizationAlgorithm

        AlgorithmFactory.register("anime_optimization", AnimeOptimizationAlgorithm)
        return
    raise ValueError(f"Unsupported stage-worker algorithm type: {algorithm_type!r}")


def backend_name(backend: Any) -> str:
    get_name = getattr(backend, "get_name", None)
    if callable(get_name):
        return str(get_name())
    return "numpy"


__all__ = [
    "AlgorithmFactory",
    "AlgorithmFactoryFn",
    "BackendFactoryFn",
    "backend_name",
    "create_algorithm",
    "create_backend",
    "register_single_algorithm",
]
