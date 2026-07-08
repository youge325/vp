from __future__ import annotations

import queue
import threading
from typing import Any

import numpy as np

from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_algorithms import PipelineAlgorithms
from app.processing.streaming.processor_streams import (
    drain_decoded,
    process_interpolated_stream,
    process_sequence_stream,
    process_single_frame_stream,
)
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _DECODE_END,
    _ENCODE_END,
)
from app.processing.streaming.stage_runtime import StepAlgorithm


class _CountingBackend:
    def __init__(self) -> None:
        self.to_tensor_calls = 0
        self.to_numpy_calls = 0

    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, Any]:
        self.to_tensor_calls += 1
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, Any]) -> np.ndarray:
        self.to_numpy_calls += 1
        return tensor["tensor"].copy()


class _AddTensor:
    def __init__(self, value: int) -> None:
        self.value = value

    def process_frame(self, tensor: dict[str, Any]) -> dict[str, Any]:
        return {"tensor": (tensor["tensor"].astype(np.uint16) + self.value).clip(0, 255).astype(np.uint8)}


class _MidpointInterpolation:
    def process_frame_pair(
        self,
        prev_tensor: dict[str, Any],
        current_tensor: dict[str, Any],
        *,
        timestep: float = 0.5,
    ) -> dict[str, Any]:
        prev = prev_tensor["tensor"].astype(np.float32)
        cur = current_tensor["tensor"].astype(np.float32)
        return {"tensor": np.rint(prev + (cur - prev) * timestep).astype(np.uint8)}


class _SequenceAlgorithm:
    def needs_frame_sequence(self) -> bool:
        return True

    def process_frame_sequence(self, frames):
        return [frame + 1 for frame in frames]


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _step(algorithm_type: str, *, multi: int | None = None) -> ProcessingStep:
    return ProcessingStep(
        algorithm_type=algorithm_type,  # type: ignore[arg-type]
        algorithm_kwargs={"multi": multi} if multi is not None else {},
        stage_name=algorithm_type,
    )


def _decoded_queue(values: list[int]) -> queue.Queue[Any]:
    decode_queue: queue.Queue[Any] = queue.Queue()
    for index, value in enumerate(values):
        decode_queue.put(DecodedFrame(source_index=index, frame=_frame(value)))
    decode_queue.put(_DECODE_END)
    return decode_queue


def _drain_encode_queue(encode_queue: queue.Queue[Any]) -> list[Any]:
    items: list[Any] = []
    while not encode_queue.empty():
        items.append(encode_queue.get_nowait())
    return items


def test_drain_decoded_yields_only_decoded_frames_until_sentinel() -> None:
    decode_queue: queue.Queue[Any] = queue.Queue()
    decode_queue.put(object())
    decode_queue.put(DecodedFrame(source_index=0, frame=_frame(10)))
    decode_queue.put(_DECODE_END)

    frames = list(drain_decoded(decode_queue, threading.Event()))

    assert [frame.source_index for frame in frames] == [0]


def test_single_frame_stream_emits_boundaries_and_stream_end() -> None:
    backend = _CountingBackend()
    step = _step("super_resolution")
    encode_queue: queue.Queue[Any] = queue.Queue()

    process_single_frame_stream(
        stage_plan=StagePlan(
            pre_steps=[step],
            interpolation_step=None,
            post_steps=[],
            total_output_frames=2,
            total_encoded_frames=2,
            total_pairs=1,
        ),
        algorithms=PipelineAlgorithms(
            pre=[StepAlgorithm(step=step, backend=backend, algorithm=_AddTensor(2))],
            interpolation=None,
            post=[],
        ),
        progress_callbacks=[lambda *_: None],
        source_frames=2,
        resume_output_frames=5,
        decode_queue=_decoded_queue([10, 20]),
        encode_queue=encode_queue,
        stop_event=threading.Event(),
        metrics=PipelineMetrics(),
    )

    items = _drain_encode_queue(encode_queue)
    encoded = [item for item in items if isinstance(item, EncodedFrame)]
    boundaries = [item for item in items if isinstance(item, SegmentBoundary)]
    assert [item.output_index for item in encoded] == [5, 6]
    assert [int(item.frame[0, 0, 0]) for item in encoded] == [12, 22]
    assert [boundary.next_source_frame for boundary in boundaries] == [1]
    assert isinstance(items[-2], StreamEnd)
    assert items[-1] is _ENCODE_END


def test_interpolated_stream_reuses_tensor_payloads_across_pairs() -> None:
    backend = _CountingBackend()
    interpolation_step = _step("frame_interpolation", multi=2)
    encode_queue: queue.Queue[Any] = queue.Queue()

    process_interpolated_stream(
        stage_plan=StagePlan(
            pre_steps=[],
            interpolation_step=interpolation_step,
            post_steps=[],
            total_output_frames=5,
            total_encoded_frames=5,
            total_pairs=2,
        ),
        algorithms=PipelineAlgorithms(
            pre=[],
            interpolation=StepAlgorithm(step=interpolation_step, backend=backend, algorithm=_MidpointInterpolation()),
            post=[],
        ),
        progress_callbacks=[lambda *_: None],
        source_frames=3,
        resume_output_frames=0,
        decode_queue=_decoded_queue([0, 60, 120]),
        encode_queue=encode_queue,
        stop_event=threading.Event(),
        metrics=PipelineMetrics(),
    )

    encoded = [item for item in _drain_encode_queue(encode_queue) if isinstance(item, EncodedFrame)]
    assert [int(item.frame[0, 0, 0]) for item in encoded] == [0, 30, 60, 90, 120]
    assert backend.to_tensor_calls == 3


def test_sequence_stream_applies_ordered_algorithm_entries() -> None:
    step = _step("super_resolution")
    encode_queue: queue.Queue[Any] = queue.Queue()
    progress_calls: list[tuple[int, int]] = []

    process_sequence_stream(
        stage_plan=StagePlan(
            pre_steps=[step],
            interpolation_step=None,
            post_steps=[],
            total_output_frames=2,
            total_encoded_frames=2,
            total_pairs=1,
        ),
        algorithms=PipelineAlgorithms(
            pre=[StepAlgorithm(step=step, backend=None, algorithm=_SequenceAlgorithm())],
            interpolation=None,
            post=[],
        ),
        progress_callbacks=[lambda current, total: progress_calls.append((current, total))],
        source_frames=2,
        resume_output_frames=0,
        decode_queue=_decoded_queue([1, 2]),
        encode_queue=encode_queue,
        stop_event=threading.Event(),
        metrics=PipelineMetrics(),
    )

    encoded = [item for item in _drain_encode_queue(encode_queue) if isinstance(item, EncodedFrame)]
    assert [int(item.frame[0, 0, 0]) for item in encoded] == [2, 3]
    assert progress_calls == [(1, 2), (2, 2)]
