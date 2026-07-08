from __future__ import annotations

from typing import Any

from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.processor_algorithms import (
    PipelineAlgorithms,
    initialize_algorithms,
    ordered_algorithm_entries,
    pipeline_needs_sequence,
    resolve_processor_mode,
)
from app.processing.streaming.stage_runtime import StepAlgorithm


class _Algorithm:
    def __init__(self, *, needs_sequence: bool = False) -> None:
        self._needs_sequence = needs_sequence

    def needs_frame_sequence(self) -> bool:
        return self._needs_sequence


def _step(
    algorithm_type: str,
    *,
    stage_name: str,
    algorithm_kwargs: dict[str, Any] | None = None,
) -> ProcessingStep:
    return ProcessingStep(
        algorithm_type=algorithm_type,  # type: ignore[arg-type]
        algorithm_kwargs=algorithm_kwargs or {},
        stage_name=stage_name,
    )


def _entry(stage_name: str, *, needs_sequence: bool = False) -> StepAlgorithm:
    return StepAlgorithm(
        step=_step("super_resolution", stage_name=stage_name),
        backend=f"backend:{stage_name}",
        algorithm=_Algorithm(needs_sequence=needs_sequence),
    )


def _stage_plan(
    *,
    pre_steps: list[ProcessingStep] | None = None,
    interpolation_step: ProcessingStep | None = None,
    post_steps: list[ProcessingStep] | None = None,
) -> StagePlan:
    return StagePlan(
        pre_steps=pre_steps or [],
        interpolation_step=interpolation_step,
        post_steps=post_steps or [],
        total_output_frames=10,
        total_encoded_frames=10,
        total_pairs=9,
    )


def test_initialize_algorithms_uses_step_backends_and_filters_create_kwargs() -> None:
    created: list[dict[str, Any]] = []
    backend_creates: list[str] = []

    def backend_getter(cache: dict[str, Any], name: str) -> str:
        if name not in cache:
            backend_creates.append(name)
            cache[name] = f"backend:{name}"
        return cache[name]

    def algorithm_factory(**kwargs: Any) -> _Algorithm:
        created.append(kwargs)
        return _Algorithm()

    stage_plan = _stage_plan(
        pre_steps=[
            _step(
                "super_resolution",
                stage_name="sr",
                algorithm_kwargs={"scale_factor": 2, "tensor_backend": "onnx"},
            ),
            _step("frame_filter_chain", stage_name="filter"),
        ],
        interpolation_step=_step(
            "frame_interpolation",
            stage_name="interp",
            algorithm_kwargs={"multi": 3, "tensor_backend": "onnx"},
        ),
        post_steps=[
            _step(
                "anime_optimization",
                stage_name="anime",
                algorithm_kwargs={"strength": 0.4, "tensor_backend": "paddle"},
            ),
        ],
    )

    algorithms = initialize_algorithms(
        stage_plan,
        "pytorch",
        algorithm_factory=algorithm_factory,
        backend_getter=backend_getter,
    )

    assert [entry.step.stage_name for entry in ordered_algorithm_entries(algorithms)] == [
        "sr",
        "filter",
        "interp",
        "anime",
    ]
    assert backend_creates == ["onnx", "pytorch", "paddle"]
    assert algorithms.pre[0].backend == "backend:onnx"
    assert algorithms.pre[1].backend == "backend:pytorch"
    assert algorithms.interpolation is not None
    assert algorithms.interpolation.backend == "backend:onnx"
    assert algorithms.post[0].backend == "backend:paddle"
    assert created[0] == {
        "algorithm_type": "super_resolution",
        "tensor_backend": "backend:onnx",
        "tensor_backend_name": "onnx",
        "scale_factor": 2,
    }
    assert created[2] == {
        "algorithm_type": "frame_interpolation",
        "tensor_backend": "backend:onnx",
        "tensor_backend_name": "onnx",
        "multi": 3,
    }


def test_ordered_algorithm_entries_returns_pre_interpolation_post_order() -> None:
    algorithms = PipelineAlgorithms(
        pre=[_entry("pre-a"), _entry("pre-b")],
        interpolation=_entry("interp"),
        post=[_entry("post")],
    )

    assert [entry.step.stage_name for entry in ordered_algorithm_entries(algorithms)] == [
        "pre-a",
        "pre-b",
        "interp",
        "post",
    ]


def test_pipeline_needs_sequence_when_any_algorithm_needs_frame_sequence() -> None:
    assert pipeline_needs_sequence(
        PipelineAlgorithms(
            pre=[_entry("pre")],
            interpolation=None,
            post=[_entry("vsr", needs_sequence=True)],
        )
    )
    assert not pipeline_needs_sequence(PipelineAlgorithms(pre=[_entry("pre")], interpolation=_entry("interp"), post=[]))


def test_resolve_processor_mode_prefers_sequence_then_stream_shape() -> None:
    interpolation_step = _step("frame_interpolation", stage_name="interp")

    assert (
        resolve_processor_mode(
            _stage_plan(),
            PipelineAlgorithms(pre=[_entry("vsr", needs_sequence=True)], interpolation=None, post=[]),
        )
        == "sequence"
    )
    assert (
        resolve_processor_mode(
            _stage_plan(),
            PipelineAlgorithms(pre=[_entry("pre")], interpolation=None, post=[]),
        )
        == "single_frame"
    )
    assert (
        resolve_processor_mode(
            _stage_plan(interpolation_step=interpolation_step),
            PipelineAlgorithms(pre=[], interpolation=_entry("interp"), post=[]),
        )
        == "interpolated"
    )
