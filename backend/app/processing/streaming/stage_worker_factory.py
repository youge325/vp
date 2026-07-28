"""Algorithm and backend factories for isolated stage workers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.algorithms.interfaces import Algorithm
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from app.planning import ProcessingStep
from app.processing.streaming.stage_rules import algorithm_kwargs_for_create

if TYPE_CHECKING:
    from app.processing.streaming.stage_worker_config import StageWorkerConfig


def create_backend(config: StageWorkerConfig) -> ITensorBackend | None:
    if config.stage.algorithm_type == "frame_filter_chain" or config.stage.execution_mode == "sequence":
        return None
    if config.tensor_backend_name is None:
        raise RuntimeError(f"Stage '{config.stage_name}' requires a tensor backend.")
    return get_tensor_backend(config.tensor_backend_name)


def create_algorithm(stage: ProcessingStep, backend: ITensorBackend | None) -> Algorithm:
    if stage.algorithm_type == "frame_filter_chain":
        from app.processing.frame_filters import FrameFilterChainAlgorithm

        return FrameFilterChainAlgorithm(tensor_backend=None, **stage.algorithm_kwargs)

    if stage.algorithm_type == "frame_interpolation":
        from app.processing.interpolation import FrameInterpolationAlgorithm

        if backend is None:
            raise RuntimeError("Frame interpolation requires a tensor backend.")
        return FrameInterpolationAlgorithm(tensor_backend=backend, **algorithm_kwargs_for_create(stage))

    if stage.algorithm_type == "super_resolution":
        from app.processing.super_resolution import OnnxSuperResolution, PaddleGanVideoSuperResolution

        kwargs = algorithm_kwargs_for_create(stage)
        if stage.execution_mode == "sequence":
            return PaddleGanVideoSuperResolution(**kwargs)
        if backend is None:
            raise RuntimeError("ONNX super-resolution requires a tensor backend.")
        return OnnxSuperResolution(**kwargs)

    raise ValueError(f"Unsupported stage-worker algorithm type: {stage.algorithm_type!r}")


__all__ = [
    "create_algorithm",
    "create_backend",
]
