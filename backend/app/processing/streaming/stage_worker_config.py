"""Domain conversion at the generated stage-worker contract boundary."""

from __future__ import annotations

from pathlib import Path

from app.generated.stage_worker_contracts import (
    StageWorkerConfig,
    StageWorkerFilterChainStep,
    StageWorkerInterpolationStep,
    StageWorkerOnnxSuperResolutionStep,
    StageWorkerPaddleSuperResolutionStep,
    StageWorkerPytorchVsrStep,
)
from app.catalog.tensor_capabilities import supports_backend_engine
from app.planning.processing_steps import ProcessingStep


def load_stage_worker_config(path: str | Path) -> StageWorkerConfig:
    config = StageWorkerConfig.model_validate_json(
        Path(path).read_text(encoding="utf-8"),
        by_alias=True,
        by_name=False,
    )
    processing_step_from_config(config)
    return config


def build_stage_worker_step(
    step: ProcessingStep,
) -> (
    StageWorkerInterpolationStep
    | StageWorkerOnnxSuperResolutionStep
    | StageWorkerPaddleSuperResolutionStep
    | StageWorkerPytorchVsrStep
    | StageWorkerFilterChainStep
):
    """Project a domain step without duplicating the top-level backend field."""
    payload = step.to_jsonable()
    payload.pop("stage_name")
    kwargs = payload["algorithm_kwargs"]
    kwargs.pop("tensor_backend", None)
    factory_key = step.descriptor.factory_key
    if factory_key == "rife":
        kwargs.pop("algorithm", None)
        return StageWorkerInterpolationStep.model_validate(payload)
    if factory_key == "onnx_super_resolution":
        kwargs.pop("scale_factor", None)
        kwargs.pop("num_frames", None)
        return StageWorkerOnnxSuperResolutionStep.model_validate(payload)
    if factory_key == "paddlegan_vsr":
        kwargs.pop("scale_factor", None)
        kwargs.pop("onnx_model", None)
        return StageWorkerPaddleSuperResolutionStep.model_validate(payload)
    if factory_key == "real_rawvsr_rgb":
        kwargs.pop("onnx_model", None)
        return StageWorkerPytorchVsrStep.model_validate(payload)
    if factory_key == "filter_chain":
        return StageWorkerFilterChainStep.model_validate(payload)
    raise ValueError(f"Stage worker protocol has no payload for factory {factory_key!r}.")


def processing_step_from_config(config: StageWorkerConfig) -> ProcessingStep:
    stage = config.stage
    if config.stage_index > config.stage_total:
        raise ValueError("Stage worker stageIndex must not exceed stageTotal.")
    if stage.algorithm_type == "frame_filter_chain" and config.tensor_backend_name is not None:
        raise ValueError("Frame-filter stage must not consume a tensor backend.")
    if stage.algorithm_type != "frame_filter_chain" and config.tensor_backend_name is None:
        raise ValueError(f"Stage worker {stage.algorithm_type.value!r} requires a tensor backend.")
    # Generated stage-worker models use Python field names internally, but
    # ProcessingStep and filter handlers consume the canonical wire keys.
    algorithm_kwargs = stage.algorithm_kwargs.model_dump(mode="json", by_alias=True, exclude_unset=True)
    if config.tensor_backend_name is not None:
        algorithm_kwargs["tensor_backend"] = config.tensor_backend_name
    step = ProcessingStep(
        algorithm_type=stage.algorithm_type,
        algorithm_kwargs=algorithm_kwargs,
        stage_name=config.stage_name,
    )
    if (
        config.tensor_backend_name is not None
        and config.tensor_backend_name.value not in step.descriptor.supported_backends
    ):
        raise ValueError(
            f"Stage worker {stage.algorithm_type!r} does not support backend {config.tensor_backend_name.value!r}."
        )
    if config.tensor_backend_name is not None:
        engine = str(step.algorithm_kwargs["engine"])
        if not supports_backend_engine(config.tensor_backend_name.value, engine):
            raise ValueError(
                f"Stage worker backend {config.tensor_backend_name.value!r} does not support engine {engine!r}."
            )
    return step


__all__ = ["build_stage_worker_step", "load_stage_worker_config", "processing_step_from_config"]
