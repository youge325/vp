"""Stage-chain execution helpers for the in-process streaming processor."""

from __future__ import annotations

from typing import Callable

from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import DecodedFrame
from app.processing.streaming.stage_runtime import (
    StepAlgorithm,
    entry_needs_sequence,
    is_cpu_frame_stage,
    run_stage,
    should_prefer_tensor_stage,
)


def run_sequence_pipeline(
    *,
    entries: list[StepAlgorithm],
    payloads: list[FramePayload],
    progress_callbacks: list[Callable[[int, int], None]],
    metrics: PipelineMetrics,
) -> list[FramePayload]:
    for stage_index, entry in enumerate(entries):
        callback = progress_callbacks[stage_index] if stage_index < len(progress_callbacks) else None
        if entry_needs_sequence(entry):
            payloads = run_sequence_stage(
                entry=entry,
                payloads=payloads,
                callback=callback,
                metrics=metrics,
            )
            continue
        if entry.algorithm.needs_frame_pairs():
            payloads = run_interpolation_sequence_stage(
                entry=entry,
                payloads=payloads,
                callback=callback,
                metrics=metrics,
            )
            continue
        payloads = run_per_frame_sequence_stage(
            entry=entry,
            payloads=payloads,
            callback=callback,
            metrics=metrics,
        )
    return payloads


def run_sequence_stage(
    *,
    entry: StepAlgorithm,
    payloads: list[FramePayload],
    callback: Callable[[int, int], None] | None,
    metrics: PipelineMetrics,
) -> list[FramePayload]:
    frames = [payload.ensure_numpy(metrics) for payload in payloads]
    with metrics.timed("process"):
        output_frames = entry.algorithm.process_frame_sequence(frames)
    output_payloads = [FramePayload.from_numpy(frame) for frame in output_frames]
    emit_stage_progress(callback, len(output_payloads))
    return output_payloads


def run_interpolation_sequence_stage(
    *,
    entry: StepAlgorithm,
    payloads: list[FramePayload],
    callback: Callable[[int, int], None] | None,
    metrics: PipelineMetrics,
) -> list[FramePayload]:
    if len(payloads) < 2:
        emit_stage_progress(callback, len(payloads))
        return payloads

    multi = int(entry.algorithm.get_interpolation_multi())
    output_payloads: list[FramePayload] = []
    total_pairs = max(len(payloads) - 1, 1)
    with metrics.timed("interpolate"):
        for pair_index in range(len(payloads) - 1):
            prev_payload = payloads[pair_index]
            current_payload = payloads[pair_index + 1]
            prev_tensor = prev_payload.ensure_tensor(entry.backend, metrics)
            current_tensor = current_payload.ensure_tensor(entry.backend, metrics)
            output_payloads.append(prev_payload)
            for mid_index in range(1, multi):
                timestep = mid_index / multi
                mid_tensor = entry.algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
                output_payloads.append(FramePayload.from_tensor(mid_tensor, entry.backend))
            if callback is not None:
                callback(pair_index + 1, total_pairs)
    output_payloads.append(payloads[-1])
    return output_payloads


def run_per_frame_sequence_stage(
    *,
    entry: StepAlgorithm,
    payloads: list[FramePayload],
    callback: Callable[[int, int], None] | None,
    metrics: PipelineMetrics,
) -> list[FramePayload]:
    output_payloads: list[FramePayload] = []
    total = len(payloads)
    with metrics.timed("process"):
        for index, payload in enumerate(payloads):
            output_payloads.append(
                run_stage(
                    entry,
                    payload,
                    metrics,
                    prefer_tensor=not is_cpu_frame_stage(entry),
                )
            )
            if callback is not None:
                callback(index + 1, total)
    return output_payloads


def emit_stage_progress(callback: Callable[[int, int], None] | None, total: int) -> None:
    if callback is None:
        return
    denominator = max(total, 1)
    for current in range(1, total + 1):
        callback(current, denominator)


def apply_post_steps(
    *,
    post_algorithms: list[StepAlgorithm],
    post_callbacks: list[Callable[[int, int], None]],
    payload: FramePayload,
    output_index: int,
    total_output_frames_denominator: int,
    metrics: PipelineMetrics,
) -> FramePayload:
    """Apply post steps while preserving tensor payloads across tensor stages."""
    return apply_stage_chain(
        algorithms=post_algorithms,
        progress_callbacks=post_callbacks,
        payload=payload,
        progress_current=output_index + 1,
        progress_total=total_output_frames_denominator,
        has_tensor_stage_after_chain=False,
        metrics=metrics,
    )


def apply_stage_chain(
    *,
    algorithms: list[StepAlgorithm],
    progress_callbacks: list[Callable[[int, int], None]],
    payload: FramePayload,
    progress_current: int,
    progress_total: int,
    has_tensor_stage_after_chain: bool,
    metrics: PipelineMetrics,
) -> FramePayload:
    """Run CPU and tensor stages in order, converting only at explicit boundaries."""
    if not algorithms:
        return payload

    with metrics.timed("process"):
        for step_index, entry in enumerate(algorithms):
            payload = run_stage(
                entry,
                payload,
                metrics,
                prefer_tensor=should_prefer_tensor_stage(
                    entry=entry,
                    payload=payload,
                    remaining=algorithms[step_index + 1 :],
                    has_tensor_stage_after_chain=has_tensor_stage_after_chain,
                ),
            )
            if step_index < len(progress_callbacks):
                progress_callbacks[step_index](progress_current, progress_total)
    return payload


def apply_pre_steps(
    *,
    pre_algorithms: list[StepAlgorithm],
    progress_callbacks: list[Callable[[int, int], None]],
    item: DecodedFrame,
    source_frames: int,
    has_tensor_stage_after_chain: bool,
    metrics: PipelineMetrics,
) -> FramePayload:
    """Run every pre-step algorithm on a decoded frame, reporting per-step progress."""
    return apply_stage_chain(
        algorithms=pre_algorithms,
        progress_callbacks=progress_callbacks,
        payload=FramePayload.from_numpy(item.frame),
        progress_current=item.source_index + 1,
        progress_total=max(source_frames, 1),
        has_tensor_stage_after_chain=has_tensor_stage_after_chain,
        metrics=metrics,
    )


__all__ = [
    "apply_post_steps",
    "apply_pre_steps",
    "apply_stage_chain",
    "emit_stage_progress",
    "run_interpolation_sequence_stage",
    "run_per_frame_sequence_stage",
    "run_sequence_pipeline",
    "run_sequence_stage",
]
