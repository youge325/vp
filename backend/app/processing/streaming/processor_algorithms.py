"""Algorithm assembly and processor-mode rules for streaming processors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from app.algorithms.factory import AlgorithmFactory
from app.planning import StagePlan
from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.stage_rules import algorithm_kwargs_for_create, stage_tensor_backend_name
from app.processing.streaming.stage_runtime import StepAlgorithm, entry_needs_sequence, get_cached_backend

ProcessorMode = Literal["sequence", "single_frame", "interpolated"]
AlgorithmFactoryFn = Callable[..., Any]
BackendGetterFn = Callable[[dict[str, Any], str], Any]


@dataclass(slots=True)
class PipelineAlgorithms:
    pre: list[StepAlgorithm]
    interpolation: StepAlgorithm | None
    post: list[StepAlgorithm]


def initialize_algorithms(
    stage_plan: StagePlan,
    tensor_backend_name: str,
    *,
    algorithm_factory: AlgorithmFactoryFn = AlgorithmFactory.create,
    backend_getter: BackendGetterFn = get_cached_backend,
) -> PipelineAlgorithms:
    algorithms = PipelineAlgorithms(pre=[], interpolation=None, post=[])
    backend_cache: dict[str, Any] = {}

    for step in stage_plan.pre_steps:
        algorithms.pre.append(
            _create_step_algorithm(
                step=step,
                default_backend_name=tensor_backend_name,
                backend_cache=backend_cache,
                algorithm_factory=algorithm_factory,
                backend_getter=backend_getter,
            )
        )

    if stage_plan.interpolation_step is not None:
        algorithms.interpolation = _create_step_algorithm(
            step=stage_plan.interpolation_step,
            default_backend_name=tensor_backend_name,
            backend_cache=backend_cache,
            algorithm_factory=algorithm_factory,
            backend_getter=backend_getter,
        )

    for step in stage_plan.post_steps:
        algorithms.post.append(
            _create_step_algorithm(
                step=step,
                default_backend_name=tensor_backend_name,
                backend_cache=backend_cache,
                algorithm_factory=algorithm_factory,
                backend_getter=backend_getter,
            )
        )

    return algorithms


def ordered_algorithm_entries(algorithms: PipelineAlgorithms) -> list[StepAlgorithm]:
    entries = list(algorithms.pre)
    if algorithms.interpolation is not None:
        entries.append(algorithms.interpolation)
    entries.extend(algorithms.post)
    return entries


def pipeline_needs_sequence(algorithms: PipelineAlgorithms) -> bool:
    return any(entry_needs_sequence(entry) for entry in ordered_algorithm_entries(algorithms))


def resolve_processor_mode(stage_plan: StagePlan, algorithms: PipelineAlgorithms) -> ProcessorMode:
    if pipeline_needs_sequence(algorithms):
        return "sequence"
    if stage_plan.interpolation_step is None:
        return "single_frame"
    return "interpolated"


def _create_step_algorithm(
    *,
    step: ProcessingStep,
    default_backend_name: str,
    backend_cache: dict[str, Any],
    algorithm_factory: AlgorithmFactoryFn,
    backend_getter: BackendGetterFn,
) -> StepAlgorithm:
    step_backend_name = stage_tensor_backend_name(step, default_backend_name)
    backend = backend_getter(backend_cache, step_backend_name)
    algorithm = algorithm_factory(
        algorithm_type=step.algorithm_type,
        tensor_backend=backend,
        tensor_backend_name=step_backend_name,
        **algorithm_kwargs_for_create(step),
    )
    return StepAlgorithm(step=step, backend=backend, algorithm=algorithm)


__all__ = [
    "PipelineAlgorithms",
    "ProcessorMode",
    "initialize_algorithms",
    "ordered_algorithm_entries",
    "pipeline_needs_sequence",
    "resolve_processor_mode",
]
