"""Shared per-stage runtime helpers for in-process and isolated workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np

from app.algorithms.interfaces import SingleFrameAlgorithm
from app.algorithms.tensor_backend import ITensorBackend
from app.planning import ProcessingStep
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics


@dataclass(slots=True)
class StepAlgorithm:
    step: ProcessingStep
    backend: ITensorBackend | None
    algorithm: SingleFrameAlgorithm


@runtime_checkable
class _FrameFilterRuntime(Protocol):
    def can_process_tensor(self, backend: ITensorBackend) -> bool: ...

    def process_tensor(self, tensor: Any, backend: ITensorBackend) -> Any: ...

    def process_numpy(self, frame: np.ndarray) -> np.ndarray: ...


def is_cpu_frame_stage(entry: StepAlgorithm) -> bool:
    return entry.step.algorithm_type == "frame_filter_chain"


def run_stage(
    entry: StepAlgorithm,
    payload: FramePayload,
    metrics: PipelineMetrics,
    *,
    prefer_tensor: bool,
) -> FramePayload:
    if is_cpu_frame_stage(entry):
        return _run_frame_filter_stage(entry, payload, metrics, prefer_tensor=prefer_tensor)
    return _run_tensor_frame_stage(entry, payload, metrics)


def _run_frame_filter_stage(
    entry: StepAlgorithm,
    payload: FramePayload,
    metrics: PipelineMetrics,
    *,
    prefer_tensor: bool,
) -> FramePayload:
    if not isinstance(entry.algorithm, _FrameFilterRuntime):
        raise RuntimeError(f"Frame filter stage '{entry.step.algorithm_type}' has an invalid runtime implementation.")
    if prefer_tensor:
        backend = _require_tensor_backend(entry)
        if not entry.algorithm.can_process_tensor(backend):
            raise RuntimeError(
                f"Frame filter stage '{entry.step.algorithm_type}' does not support tensor processing "
                "in this tensor chain."
            )
        tensor = payload.ensure_tensor(backend, metrics)
        return FramePayload.from_tensor(entry.algorithm.process_tensor(tensor, backend), backend)
    return _run_cpu_frame_stage(entry, payload, metrics)


def _run_cpu_frame_stage(entry: StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    if not isinstance(entry.algorithm, _FrameFilterRuntime):
        raise RuntimeError(f"CPU frame stage '{entry.step.algorithm_type}' does not implement process_numpy().")
    frame = payload.ensure_numpy(metrics)
    return FramePayload.from_numpy(entry.algorithm.process_numpy(frame))


def _run_tensor_frame_stage(entry: StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    backend = _require_tensor_backend(entry)
    tensor = payload.ensure_tensor(backend, metrics)
    processed = entry.algorithm.process_frame(tensor)
    return FramePayload.from_tensor(processed, backend)


def _require_tensor_backend(entry: StepAlgorithm) -> ITensorBackend:
    if entry.backend is None:
        raise RuntimeError(f"Tensor stage '{entry.step.algorithm_type}' requires a tensor backend.")
    return entry.backend


__all__ = [
    "StepAlgorithm",
    "is_cpu_frame_stage",
    "run_stage",
]
