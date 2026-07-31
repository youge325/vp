"""Shared per-stage runtime helpers for in-process and isolated workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from app.algorithms.interfaces import NumpyFrameAlgorithm, SingleFrameAlgorithm
from app.algorithms.tensor_backend import ITensorBackend
from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics


@dataclass(slots=True)
class StepAlgorithm:
    step: ProcessingStep
    backend: ITensorBackend | None
    algorithm: SingleFrameAlgorithm | NumpyFrameAlgorithm


@runtime_checkable
class _FrameFilterRuntime(Protocol):
    def process_numpy(self, frame: np.ndarray) -> np.ndarray: ...


def _is_cpu_frame_stage(entry: StepAlgorithm) -> bool:
    return entry.step.algorithm_type == "frame_filter_chain"


def run_stage(
    entry: StepAlgorithm,
    payload: FramePayload,
    metrics: PipelineMetrics,
) -> FramePayload:
    if _is_cpu_frame_stage(entry):
        return _run_cpu_frame_stage(entry, payload, metrics)
    return _run_tensor_frame_stage(entry, payload, metrics)


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
    "run_stage",
]
