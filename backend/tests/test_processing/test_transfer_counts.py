"""Transfer-count regression tests for the streaming processor."""

from __future__ import annotations

import queue
import threading
from typing import Any

import numpy as np
import pytest

from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_algorithms import PipelineAlgorithms
from app.processing.streaming.processor_stream_interpolated import (
    process_interpolated_stream,
)
from app.processing.streaming.processor_stream_single import process_single_frame_stream
from app.processing.streaming.queues import DecodedFrame, EncodedFrame, _DECODE_END
from app.processing.streaming.stage_runtime import StepAlgorithm


class _CountingBackend:
    def __init__(self) -> None:
        self.to_tensor_calls = 0
        self.to_numpy_calls = 0

    def get_name(self) -> str:
        return "counting"

    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, Any]:
        self.to_tensor_calls += 1
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, Any]) -> np.ndarray:
        self.to_numpy_calls += 1
        return tensor["tensor"].copy()


class _AddTensor:
    def __init__(self, value: int = 1) -> None:
        self.value = value

    def process_frame(self, tensor: dict[str, Any]) -> dict[str, Any]:
        return {"tensor": _add(tensor["tensor"], self.value)}


class _AddCpuFilter:
    def __init__(self, value: int = 1) -> None:
        self.value = value

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        return _add(frame, self.value)


class _AddTensorFilter(_AddCpuFilter):
    def can_process_tensor(self, backend: Any) -> bool:
        del backend
        return True

    def process_tensor(self, tensor: dict[str, Any], backend: Any) -> dict[str, Any]:
        del backend
        return {"tensor": _add(tensor["tensor"], self.value)}


class _TensorOnlyFilter:
    def __init__(self, value: int = 1) -> None:
        self.value = value

    def can_process_tensor(self, backend: Any) -> bool:
        del backend
        return True

    def process_tensor(self, tensor: dict[str, Any], backend: Any) -> dict[str, Any]:
        del backend
        return {"tensor": _add(tensor["tensor"], self.value)}

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        del frame
        raise AssertionError("tensor-only filter should not be executed as a CPU stage")


class _UnsupportedTensorFilter(_AddCpuFilter):
    def can_process_tensor(self, backend: Any) -> bool:
        del backend
        return False


class _MidpointInterpolation:
    def process_frame_pair(
        self,
        prev_tensor: dict[str, Any],
        current_tensor: dict[str, Any],
        *,
        timestep: float = 0.5,
    ) -> dict[str, Any]:
        del timestep
        prev = prev_tensor["tensor"].astype(np.float32)
        cur = current_tensor["tensor"].astype(np.float32)
        return {"tensor": ((prev + cur) / 2).astype(np.uint8)}


def _add(frame: np.ndarray, value: int) -> np.ndarray:
    return (frame.astype(np.uint16) + value).clip(0, 255).astype(np.uint8)


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _step(algorithm_type: str, *, multi: int | None = None) -> ProcessingStep:
    kwargs = {"multi": multi} if multi is not None else {}
    return ProcessingStep(
        algorithm_type=algorithm_type,  # type: ignore[arg-type]
        algorithm_kwargs=kwargs,
        stage_name=algorithm_type,
    )


def _step_algorithm(backend: _CountingBackend, algorithm_type: str, algorithm: Any) -> StepAlgorithm:
    return StepAlgorithm(step=_step(algorithm_type), backend=backend, algorithm=algorithm)


def _decoded_queue(values: list[int]) -> queue.Queue[Any]:
    decode_queue: queue.Queue[Any] = queue.Queue()
    for index, value in enumerate(values):
        decode_queue.put(DecodedFrame(source_index=index, frame=_frame(value)))
    decode_queue.put(_DECODE_END)
    return decode_queue


def _encoded_values(encode_queue: queue.Queue[Any]) -> list[int]:
    values: list[int] = []
    while not encode_queue.empty():
        item = encode_queue.get_nowait()
        if isinstance(item, EncodedFrame):
            values.append(int(item.frame[0, 0, 0]))
    return values


def _run_single(
    *,
    pre: list[StepAlgorithm],
    source_values: list[int],
    progress_callbacks: list[Any] | None = None,
) -> tuple[_CountingBackend, PipelineMetrics, list[int]]:
    backend = pre[0].backend if pre else _CountingBackend()
    stage_plan = StagePlan(
        pre_steps=[entry.step for entry in pre],
        interpolation_step=None,
        post_steps=[],
        total_output_frames=len(source_values),
        total_encoded_frames=len(source_values),
        total_pairs=max(len(source_values) - 1, 0),
    )
    encode_queue: queue.Queue[Any] = queue.Queue()
    metrics = PipelineMetrics()
    process_single_frame_stream(
        stage_plan=stage_plan,
        algorithms=PipelineAlgorithms(pre=pre, interpolation=None, post=[]),
        progress_callbacks=progress_callbacks or [lambda *_: None for _ in pre],
        source_frames=len(source_values),
        resume_output_frames=0,
        decode_queue=_decoded_queue(source_values),
        encode_queue=encode_queue,
        stop_event=threading.Event(),
        metrics=metrics,
    )
    return backend, metrics, _encoded_values(encode_queue)


def _run_interpolated(
    *,
    backend: _CountingBackend,
    pre: list[StepAlgorithm],
    post: list[StepAlgorithm],
    source_values: list[int],
    multi: int = 2,
) -> tuple[PipelineMetrics, list[int]]:
    interpolation_step = _step("frame_interpolation", multi=multi)
    stage_plan = StagePlan(
        pre_steps=[entry.step for entry in pre],
        interpolation_step=interpolation_step,
        post_steps=[entry.step for entry in post],
        total_output_frames=(len(source_values) - 1) * multi + 1 if len(source_values) > 1 else len(source_values),
        total_encoded_frames=(len(source_values) - 1) * multi + 1 if len(source_values) > 1 else len(source_values),
        total_pairs=max(len(source_values) - 1, 0),
    )
    encode_queue: queue.Queue[Any] = queue.Queue()
    metrics = PipelineMetrics()
    callbacks = [lambda *_: None for _ in [*pre, interpolation_step, *post]]
    process_interpolated_stream(
        stage_plan=stage_plan,
        algorithms=PipelineAlgorithms(
            pre=pre,
            interpolation=StepAlgorithm(
                step=interpolation_step,
                backend=backend,
                algorithm=_MidpointInterpolation(),
            ),
            post=post,
        ),
        progress_callbacks=callbacks,
        source_frames=len(source_values),
        resume_output_frames=0,
        decode_queue=_decoded_queue(source_values),
        encode_queue=encode_queue,
        stop_event=threading.Event(),
        metrics=metrics,
    )
    return metrics, _encoded_values(encode_queue)


def test_multi_tensor_stages_do_single_h2d_and_d2h_per_frame() -> None:
    backend = _CountingBackend()
    pre = [
        _step_algorithm(backend, "anime_optimization", _AddTensor(1)),
        _step_algorithm(backend, "super_resolution", _AddTensor(1)),
    ]

    backend, metrics, values = _run_single(pre=pre, source_values=[10, 20])

    assert values == [12, 22]
    assert backend.to_tensor_calls == 2
    assert backend.to_numpy_calls == 2
    assert metrics.snapshot()["transferCounts"] == {"h2d": 2, "d2h": 2}


def test_cpu_only_filter_chain_does_not_touch_tensor_backend() -> None:
    backend = _CountingBackend()
    pre = [_step_algorithm(backend, "frame_filter_chain", _AddCpuFilter(5))]

    backend, metrics, values = _run_single(pre=pre, source_values=[10, 20])

    assert values == [15, 25]
    assert backend.to_tensor_calls == 0
    assert backend.to_numpy_calls == 0
    assert metrics.snapshot()["transferCounts"] == {"h2d": 0, "d2h": 0}


def test_legacy_cpu_filter_between_tensor_stages_fails_without_roundtrip() -> None:
    backend = _CountingBackend()
    pre = [
        _step_algorithm(backend, "anime_optimization", _AddTensor(1)),
        _step_algorithm(backend, "frame_filter_chain", _AddCpuFilter(2)),
        _step_algorithm(backend, "super_resolution", _AddTensor(3)),
    ]
    metrics = PipelineMetrics()
    stage_plan = StagePlan(
        pre_steps=[entry.step for entry in pre],
        interpolation_step=None,
        post_steps=[],
        total_output_frames=1,
        total_encoded_frames=1,
        total_pairs=0,
    )

    with pytest.raises(RuntimeError, match="does not support tensor processing"):
        process_single_frame_stream(
            stage_plan=stage_plan,
            algorithms=PipelineAlgorithms(pre=pre, interpolation=None, post=[]),
            progress_callbacks=[lambda *_: None for _ in pre],
            source_frames=1,
            resume_output_frames=0,
            decode_queue=_decoded_queue([10]),
            encode_queue=queue.Queue(),
            stop_event=threading.Event(),
            metrics=metrics,
        )

    assert backend.to_tensor_calls == 1
    assert backend.to_numpy_calls == 0
    assert metrics.snapshot()["transferCounts"] == {"h2d": 1, "d2h": 0}


def test_tensor_capable_filter_between_tensor_stages_stays_on_tensor() -> None:
    backend = _CountingBackend()
    pre = [
        _step_algorithm(backend, "anime_optimization", _AddTensor(1)),
        _step_algorithm(backend, "frame_filter_chain", _AddTensorFilter(2)),
        _step_algorithm(backend, "super_resolution", _AddTensor(3)),
    ]

    backend, metrics, values = _run_single(pre=pre, source_values=[10])

    assert values == [16]
    assert backend.to_tensor_calls == 1
    assert backend.to_numpy_calls == 1
    assert metrics.snapshot()["transferCounts"] == {"h2d": 1, "d2h": 1}


def test_tensor_capable_pre_filter_uploads_once_before_tensor_stage() -> None:
    backend = _CountingBackend()
    pre = [
        _step_algorithm(backend, "frame_filter_chain", _AddTensorFilter(2)),
        _step_algorithm(backend, "super_resolution", _AddTensor(3)),
    ]

    backend, metrics, values = _run_single(pre=pre, source_values=[10])

    assert values == [15]
    assert backend.to_tensor_calls == 1
    assert backend.to_numpy_calls == 1
    assert metrics.snapshot()["transferCounts"] == {"h2d": 1, "d2h": 1}


def test_unsupported_filter_in_tensor_chain_fails_without_roundtrip() -> None:
    backend = _CountingBackend()
    pre = [
        _step_algorithm(backend, "anime_optimization", _AddTensor(1)),
        _step_algorithm(backend, "frame_filter_chain", _UnsupportedTensorFilter(2)),
        _step_algorithm(backend, "super_resolution", _AddTensor(3)),
    ]
    metrics = PipelineMetrics()
    stage_plan = StagePlan(
        pre_steps=[entry.step for entry in pre],
        interpolation_step=None,
        post_steps=[],
        total_output_frames=1,
        total_encoded_frames=1,
        total_pairs=0,
    )

    with pytest.raises(RuntimeError, match="does not support tensor processing"):
        process_single_frame_stream(
            stage_plan=stage_plan,
            algorithms=PipelineAlgorithms(pre=pre, interpolation=None, post=[]),
            progress_callbacks=[lambda *_: None for _ in pre],
            source_frames=1,
            resume_output_frames=0,
            decode_queue=_decoded_queue([10]),
            encode_queue=queue.Queue(),
            stop_event=threading.Event(),
            metrics=metrics,
        )

    assert backend.to_tensor_calls == 1
    assert backend.to_numpy_calls == 0
    assert metrics.snapshot()["transferCounts"] == {"h2d": 1, "d2h": 0}


def test_tensor_pre_stage_flows_into_interpolation_without_reupload() -> None:
    backend = _CountingBackend()
    pre = [_step_algorithm(backend, "super_resolution", _AddTensor(10))]

    metrics, values = _run_interpolated(
        backend=backend,
        pre=pre,
        post=[],
        source_values=[0, 100],
        multi=2,
    )

    assert values == [10, 60, 110]
    assert backend.to_tensor_calls == 2
    assert backend.to_numpy_calls == 3
    assert metrics.snapshot()["transferCounts"] == {"h2d": 2, "d2h": 3}


def test_tensor_capable_pre_filter_flows_into_interpolation_without_cpu_boundary() -> None:
    backend = _CountingBackend()
    pre = [_step_algorithm(backend, "frame_filter_chain", _TensorOnlyFilter(10))]

    metrics, values = _run_interpolated(
        backend=backend,
        pre=pre,
        post=[],
        source_values=[0, 100],
        multi=2,
    )

    assert values == [10, 60, 110]
    assert backend.to_tensor_calls == 2
    assert backend.to_numpy_calls == 3
    assert metrics.snapshot()["transferCounts"] == {"h2d": 2, "d2h": 3}


def test_interpolated_midframes_enter_tensor_post_chain_without_roundtrip() -> None:
    backend = _CountingBackend()
    post = [_step_algorithm(backend, "super_resolution", _AddTensor(1))]

    metrics, values = _run_interpolated(
        backend=backend,
        pre=[],
        post=post,
        source_values=[0, 100],
        multi=2,
    )

    assert values == [1, 51, 101]
    assert backend.to_tensor_calls == 2
    assert backend.to_numpy_calls == 3
    assert metrics.snapshot()["transferCounts"] == {"h2d": 2, "d2h": 3}


def test_interpolated_midframes_enter_tensor_filter_post_chain_without_roundtrip() -> None:
    backend = _CountingBackend()
    post = [_step_algorithm(backend, "frame_filter_chain", _AddTensorFilter(1))]

    metrics, values = _run_interpolated(
        backend=backend,
        pre=[],
        post=post,
        source_values=[0, 100],
        multi=2,
    )

    assert values == [1, 51, 101]
    assert backend.to_tensor_calls == 2
    assert backend.to_numpy_calls == 3
    assert metrics.snapshot()["transferCounts"] == {"h2d": 2, "d2h": 3}
