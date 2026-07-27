"""Algorithm and backend factories for isolated stage workers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.algorithms.base import IAlgorithm
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from app.planning import ProcessingStep
from app.processing.streaming.stage_rules import algorithm_kwargs_for_create

if TYPE_CHECKING:
    from app.processing.streaming.stage_worker_config import StageWorkerConfig


def create_backend(config: StageWorkerConfig) -> ITensorBackend | None:
    if config.stage.algorithm_type == "frame_filter_chain":
        return None
    return get_tensor_backend(config.tensor_backend_name)


def create_algorithm(stage: ProcessingStep, backend: ITensorBackend | None) -> IAlgorithm:
    if stage.algorithm_type == "frame_filter_chain":
        from app.processing.frame_filters import FrameFilterChainAlgorithm

        return FrameFilterChainAlgorithm(tensor_backend=None, **stage.algorithm_kwargs)

    if stage.algorithm_type == "frame_interpolation":
        from app.processing.interpolation import FrameInterpolationAlgorithm

        algorithm_class = FrameInterpolationAlgorithm
    elif stage.algorithm_type == "super_resolution":
        from app.processing.super_resolution import SuperResolutionAlgorithm

        algorithm_class = SuperResolutionAlgorithm
    else:
        raise ValueError(f"Unsupported stage-worker algorithm type: {stage.algorithm_type!r}")
    if backend is None:
        raise RuntimeError(f"Stage-worker algorithm {stage.algorithm_type!r} requires a tensor backend.")
    return algorithm_class(tensor_backend=backend, **algorithm_kwargs_for_create(stage))


__all__ = [
    "create_algorithm",
    "create_backend",
]
