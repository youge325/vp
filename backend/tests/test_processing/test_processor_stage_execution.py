from __future__ import annotations

from typing import Any

import numpy as np

from app.planning import ProcessingStep
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_stage_execution import (
    apply_stage_chain,
    run_interpolation_sequence_stage,
    run_sequence_stage,
)
from app.processing.streaming.stage_runtime import StepAlgorithm


class _CountingBackend:
    def __init__(self) -> None:
        self.to_tensor_calls = 0
        self.to_numpy_calls = 0

    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, np.ndarray]:
        self.to_tensor_calls += 1
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, np.ndarray]) -> np.ndarray:
        self.to_numpy_calls += 1
        return tensor["tensor"].copy()


class _AddTensor:
    def __init__(self, value: int) -> None:
        self.value = value

    def process_frame(self, tensor: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        return {"tensor": _add(tensor["tensor"], self.value)}


class _AddSequence:
    def process_frame_sequence(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        return [_add(frame, 1) for frame in frames]


class _Interpolation:
    def get_interpolation_multi(self) -> int:
        return 3

    def process_frame_pair(
        self,
        prev_tensor: dict[str, np.ndarray],
        current_tensor: dict[str, np.ndarray],
        *,
        timestep: float,
    ) -> dict[str, np.ndarray]:
        prev = prev_tensor["tensor"].astype(np.float32)
        current = current_tensor["tensor"].astype(np.float32)
        return {"tensor": ((prev * (1 - timestep)) + (current * timestep)).astype(np.uint8)}


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _add(frame: np.ndarray, value: int) -> np.ndarray:
    return (frame.astype(np.uint16) + value).clip(0, 255).astype(np.uint8)


def _step(algorithm_type: str) -> ProcessingStep:
    return ProcessingStep(
        algorithm_type=algorithm_type,  # type: ignore[arg-type]
        algorithm_kwargs={},
        stage_name=algorithm_type,
    )


def _entry(backend: Any, algorithm_type: str, algorithm: Any) -> StepAlgorithm:
    return StepAlgorithm(step=_step(algorithm_type), backend=backend, algorithm=algorithm)


def test_apply_stage_chain_preserves_tensor_payloads_and_reports_progress() -> None:
    backend = _CountingBackend()
    callbacks: list[tuple[int, int]] = []
    payload = apply_stage_chain(
        algorithms=[
            _entry(backend, "super_resolution", _AddTensor(1)),
            _entry(backend, "anime_optimization", _AddTensor(2)),
        ],
        progress_callbacks=[lambda current, total: callbacks.append((current, total)) for _ in range(2)],
        payload=FramePayload.from_numpy(_frame(10)),
        progress_current=7,
        progress_total=12,
        has_tensor_stage_after_chain=False,
        metrics=PipelineMetrics(),
    )

    assert int(payload.ensure_numpy(PipelineMetrics())[0, 0, 0]) == 13
    assert backend.to_tensor_calls == 1
    assert callbacks == [(7, 12), (7, 12)]


def test_run_sequence_stage_processes_all_frames_and_emits_output_progress() -> None:
    callbacks: list[tuple[int, int]] = []
    output = run_sequence_stage(
        entry=_entry(None, "super_resolution", _AddSequence()),
        payloads=[FramePayload.from_numpy(_frame(1)), FramePayload.from_numpy(_frame(2))],
        callback=lambda current, total: callbacks.append((current, total)),
        metrics=PipelineMetrics(),
    )

    assert [int(payload.ensure_numpy(PipelineMetrics())[0, 0, 0]) for payload in output] == [2, 3]
    assert callbacks == [(1, 2), (2, 2)]


def test_run_interpolation_sequence_stage_expands_pairs_and_reports_pair_progress() -> None:
    backend = _CountingBackend()
    callbacks: list[tuple[int, int]] = []
    output = run_interpolation_sequence_stage(
        entry=_entry(backend, "frame_interpolation", _Interpolation()),
        payloads=[FramePayload.from_numpy(_frame(0)), FramePayload.from_numpy(_frame(90))],
        callback=lambda current, total: callbacks.append((current, total)),
        metrics=PipelineMetrics(),
    )

    assert [int(payload.ensure_numpy(PipelineMetrics())[0, 0, 0]) for payload in output] == [0, 30, 60, 90]
    assert callbacks == [(1, 1)]
