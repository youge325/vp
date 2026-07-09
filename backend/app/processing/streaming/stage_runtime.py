"""Shared per-stage runtime helpers for in-process and isolated workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.planning import ProcessingStep
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics


@dataclass(slots=True)
class StepAlgorithm:
    step: ProcessingStep
    backend: Any
    algorithm: Any


def algorithm_needs_sequence(algorithm: Any) -> bool:
    needs_sequence = getattr(algorithm, "needs_frame_sequence", None)
    return callable(needs_sequence) and bool(needs_sequence())


def algorithm_needs_pairs(algorithm: Any) -> bool:
    needs_pairs = getattr(algorithm, "needs_frame_pairs", None)
    return callable(needs_pairs) and bool(needs_pairs())


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
    if prefer_tensor:
        can_process_tensor = getattr(entry.algorithm, "can_process_tensor", None)
        if not callable(can_process_tensor) or not can_process_tensor(entry.backend):
            raise RuntimeError(
                f"Frame filter stage '{entry.step.algorithm_type}' does not support tensor processing "
                "in this tensor chain."
            )
        process_tensor = getattr(entry.algorithm, "process_tensor", None)
        if not callable(process_tensor):
            raise RuntimeError(f"Tensor frame stage '{entry.step.algorithm_type}' does not implement process_tensor().")
        tensor = payload.ensure_tensor(entry.backend, metrics)
        return FramePayload.from_tensor(process_tensor(tensor, entry.backend), entry.backend)
    return _run_cpu_frame_stage(entry, payload, metrics)


def _run_cpu_frame_stage(entry: StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    process_numpy = getattr(entry.algorithm, "process_numpy", None)
    if not callable(process_numpy):
        raise RuntimeError(f"CPU frame stage '{entry.step.algorithm_type}' does not implement process_numpy().")
    frame = payload.ensure_numpy(metrics)
    return FramePayload.from_numpy(process_numpy(frame))


def _run_tensor_frame_stage(entry: StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    tensor = payload.ensure_tensor(entry.backend, metrics)
    processed = entry.algorithm.process_frame(tensor)
    return FramePayload.from_tensor(processed, entry.backend)


__all__ = [
    "StepAlgorithm",
    "algorithm_needs_pairs",
    "algorithm_needs_sequence",
    "is_cpu_frame_stage",
    "run_stage",
]
