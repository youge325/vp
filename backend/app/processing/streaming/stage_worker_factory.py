"""Algorithm and backend factories for isolated stage workers."""

from __future__ import annotations

from collections.abc import Callable

from app.algorithms.interfaces import Algorithm
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.planning.processing_steps import ProcessingStep

type _AlgorithmFactory = Callable[[ProcessingStep, ITensorBackend | None, str], Algorithm]


def create_backend(config: StageWorkerConfig, step: ProcessingStep) -> ITensorBackend | None:
    if step.algorithm_type == "frame_filter_chain" or step.execution_mode == "sequence":
        return None
    if config.tensor_backend_name is None:
        raise RuntimeError(f"Stage '{config.stage_name}' requires a tensor backend.")
    return get_tensor_backend(config.tensor_backend_name)


def create_algorithm(stage: ProcessingStep, backend: ITensorBackend | None, *, model_root: str) -> Algorithm:
    if stage.algorithm_type == "frame_filter_chain":
        return _create_filter_chain(stage, backend, model_root)
    try:
        factory = _ALGORITHM_FACTORIES[stage.descriptor.factory_key]
    except KeyError as exc:  # pragma: no cover - catalog/factory set gate
        raise ValueError(f"No factory registered for {stage.descriptor.factory_key!r}.") from exc
    return factory(stage, backend, model_root)


def _create_filter_chain(stage: ProcessingStep, _backend: ITensorBackend | None, _model_root: str) -> Algorithm:
    from app.processing.frame_filters import FrameFilterChainAlgorithm

    return FrameFilterChainAlgorithm(filters=stage.algorithm_kwargs["filters"])


def _create_rife(stage: ProcessingStep, backend: ITensorBackend | None, model_root: str) -> Algorithm:
    from app.algorithms.rife_interpolation import FrameInterpolationAlgorithm

    if backend is None:
        raise RuntimeError("Frame interpolation requires a tensor backend.")
    kwargs = stage.algorithm_kwargs
    return FrameInterpolationAlgorithm(
        backend_name=kwargs["tensor_backend"],
        model_version=kwargs["model_version"],
        scale=kwargs["scale"],
        fp16=kwargs["fp16"],
        onnx_model=kwargs["onnx_model"],
        engine=kwargs["engine"],
        model_dir=model_root,
    )


def _create_onnx_super_resolution(stage: ProcessingStep, backend: ITensorBackend | None, model_root: str) -> Algorithm:
    from app.algorithms.onnx_super_resolution import OnnxSuperResolution

    if backend is None:
        raise RuntimeError("ONNX super-resolution requires a tensor backend.")
    kwargs = stage.algorithm_kwargs
    return OnnxSuperResolution(
        sr_algorithm=kwargs["sr_algorithm"],
        onnx_model=kwargs["onnx_model"],
        engine=kwargs["engine"],
        model_dir=model_root,
    )


def _create_paddlegan(stage: ProcessingStep, _backend: ITensorBackend | None, _model_root: str) -> Algorithm:
    from app.algorithms.paddle_video_super_resolution import PaddleGanVideoSuperResolution

    kwargs = stage.algorithm_kwargs
    return PaddleGanVideoSuperResolution(
        sr_algorithm=kwargs["sr_algorithm"],
        num_frames=kwargs["num_frames"],
        engine=kwargs["engine"],
    )


_ALGORITHM_FACTORIES: dict[str, _AlgorithmFactory] = {
    "rife": _create_rife,
    "onnx_super_resolution": _create_onnx_super_resolution,
    "paddlegan_vsr": _create_paddlegan,
}


__all__ = [
    "create_algorithm",
    "create_backend",
]
