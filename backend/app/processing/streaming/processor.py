"""Processor worker — runs algorithms between decode and encode queues.

Two flavours of the inner loop:

- ``_process_single_frame_stream`` for pipelines without interpolation
- ``_process_interpolated_stream`` for pipelines with a RIFE-style
  interpolation step that emits ``multi`` frames per source pair

Phase D.6.3 — 两条循环共享的样板(decoded-queue sentinel 处理、pre_steps
应用、StreamEnd + _ENCODE_END 收尾)收敛到 ``_drain_decoded`` /
``_apply_pre_steps`` / ``_emit_stream_end`` 三个 helper,但主循环
**故意保留**两份独立实现 —— "1:1 emit"与"multi:1 emit"的数据流差
异显式分开,比折叠后再用 if/else 或 Step 协议重新分支更易调试。
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _DECODE_END,
    _ENCODE_END,
    _queue_get,
    _queue_put,
    _queue_put_nowait,
)


@dataclass(slots=True)
class _StepAlgorithm:
    step: ProcessingStep
    backend: Any
    algorithm: Any


@dataclass(slots=True)
class _PipelineAlgorithms:
    pre: list[_StepAlgorithm]
    interpolation: _StepAlgorithm | None
    post: list[_StepAlgorithm]


def _processor_worker(
    *,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    try:
        algorithms = _initialize_algorithms(stage_plan, tensor_backend_name)

        if stage_plan.interpolation_step is None:
            _process_single_frame_stream(
                stage_plan=stage_plan,
                algorithms=algorithms,
                progress_callbacks=progress_callbacks,
                source_frames=source_frames,
                resume_output_frames=resume_output_frames,
                decode_queue=decode_queue,
                encode_queue=encode_queue,
                stop_event=stop_event,
                metrics=metrics,
            )
        else:
            _process_interpolated_stream(
                stage_plan=stage_plan,
                algorithms=algorithms,
                progress_callbacks=progress_callbacks,
                source_frames=source_frames,
                resume_output_frames=resume_output_frames,
                decode_queue=decode_queue,
                encode_queue=encode_queue,
                stop_event=stop_event,
                metrics=metrics,
            )
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        _queue_put_nowait(encode_queue, _ENCODE_END)


def _initialize_algorithms(stage_plan: StagePlan, tensor_backend_name: str) -> _PipelineAlgorithms:
    algorithms = _PipelineAlgorithms(pre=[], interpolation=None, post=[])

    # Re-use a single backend instance across all algorithms in the pipeline.
    # This avoids redundant DLL registration and repeated ``import onnxruntime``
    # when multiple steps share the same tensor backend.
    shared_backend = get_tensor_backend(tensor_backend_name)

    for step in stage_plan.pre_steps:
        algorithm = AlgorithmFactory.create(
            algorithm_type=step.algorithm_type,
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step.algorithm_kwargs,
        )
        algorithms.pre.append(_StepAlgorithm(step=step, backend=shared_backend, algorithm=algorithm))

    if stage_plan.interpolation_step is not None:
        step = stage_plan.interpolation_step
        algorithm = AlgorithmFactory.create(
            algorithm_type=step.algorithm_type,
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step.algorithm_kwargs,
        )
        algorithms.interpolation = _StepAlgorithm(step=step, backend=shared_backend, algorithm=algorithm)

    for step in stage_plan.post_steps:
        algorithm = AlgorithmFactory.create(
            algorithm_type=step.algorithm_type,
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step.algorithm_kwargs,
        )
        algorithms.post.append(_StepAlgorithm(step=step, backend=shared_backend, algorithm=algorithm))

    return algorithms


def _process_single_frame_stream(
    *,
    stage_plan: StagePlan,
    algorithms: _PipelineAlgorithms,
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    held: tuple[int, FramePayload] | None = None
    output_index = resume_output_frames

    for item in _drain_decoded(decode_queue, stop_event):
        payload = _apply_pre_steps(
            pre_algorithms=algorithms.pre,
            progress_callbacks=progress_callbacks,
            item=item,
            source_frames=source_frames,
            metrics=metrics,
        )

        if held is None:
            held = (item.source_index, payload)
            continue

        _held_source_index, held_payload = held
        _emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=held_payload,
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1
        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        held = (item.source_index, payload)

    if held is not None:
        _emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=held[1],
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1

    _emit_stream_end(encode_queue, source_frames, stop_event)
    del stage_plan


def _process_interpolated_stream(
    *,
    stage_plan: StagePlan,
    algorithms: _PipelineAlgorithms,
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        raise RuntimeError("Interpolation stage is required for interpolated processing.")

    pre_count = len(stage_plan.pre_steps)
    interpolation_callback = progress_callbacks[pre_count]
    post_callbacks = progress_callbacks[pre_count + 1 :]
    interpolation = algorithms.interpolation
    if interpolation is None:
        raise RuntimeError("Interpolation algorithm is required for interpolated processing.")
    interpolation_backend = interpolation.backend
    interpolation_algorithm = interpolation.algorithm
    multi = int(interpolation_step.algorithm_kwargs.get("multi") or 2)

    total_output_frames_denominator = max(stage_plan.total_output_frames, 1)

    # Keep payloads across adjacent pairs so the current tensor uploaded for
    # this pair becomes the previous tensor for the next pair.
    previous: tuple[int, FramePayload] | None = None
    output_index = resume_output_frames
    total_pairs = max(source_frames - 1, 1)

    for item in _drain_decoded(decode_queue, stop_event):
        current_payload = _apply_pre_steps(
            pre_algorithms=algorithms.pre,
            progress_callbacks=progress_callbacks,
            item=item,
            source_frames=source_frames,
            metrics=metrics,
        )

        if previous is None:
            previous = (item.source_index, current_payload)
            continue

        prev_source_index, prev_payload = previous
        interpolation_callback(prev_source_index + 1, total_pairs)

        group_payloads = [prev_payload]
        with metrics.timed("interpolate"):
            prev_tensor = prev_payload.ensure_tensor(interpolation_backend, metrics)
            current_tensor = current_payload.ensure_tensor(interpolation_backend, metrics)
            for mid_index in range(1, multi):
                timestep = mid_index / multi
                mid_tensor = interpolation_algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
                group_payloads.append(FramePayload.from_tensor(mid_tensor, interpolation_backend))

        for payload in group_payloads:
            processed_payload = _apply_post_steps(
                post_algorithms=algorithms.post,
                post_callbacks=post_callbacks,
                payload=payload,
                output_index=output_index,
                total_output_frames_denominator=total_output_frames_denominator,
                metrics=metrics,
            )
            _emit_encoded_payload(
                encode_queue=encode_queue,
                output_index=output_index,
                payload=processed_payload,
                stop_event=stop_event,
                metrics=metrics,
            )
            output_index += 1

        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        previous = (item.source_index, current_payload)

    if previous is not None:
        final_payload = previous[1]
        final_output = _apply_post_steps(
            post_algorithms=algorithms.post,
            post_callbacks=post_callbacks,
            payload=final_payload,
            output_index=output_index,
            total_output_frames_denominator=total_output_frames_denominator,
            metrics=metrics,
        )
        _emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=final_output,
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1

    _emit_stream_end(encode_queue, source_frames, stop_event)


def _apply_post_steps(
    *,
    post_algorithms: list[_StepAlgorithm],
    post_callbacks: list[Callable[[int, int], None]],
    payload: FramePayload,
    output_index: int,
    total_output_frames_denominator: int,
    metrics: PipelineMetrics,
) -> FramePayload:
    """Apply post steps while preserving tensor payloads across tensor stages."""
    return _apply_stage_chain(
        algorithms=post_algorithms,
        progress_callbacks=post_callbacks,
        payload=payload,
        progress_current=output_index + 1,
        progress_total=total_output_frames_denominator,
        metrics=metrics,
    )


def _apply_stage_chain(
    *,
    algorithms: list[_StepAlgorithm],
    progress_callbacks: list[Callable[[int, int], None]],
    payload: FramePayload,
    progress_current: int,
    progress_total: int,
    metrics: PipelineMetrics,
) -> FramePayload:
    """Run CPU and tensor stages in order, converting only at explicit boundaries."""
    if not algorithms:
        return payload

    with metrics.timed("process"):
        for step_index, entry in enumerate(algorithms):
            payload = _run_stage(entry, payload, metrics)
            if step_index < len(progress_callbacks):
                progress_callbacks[step_index](progress_current, progress_total)
    return payload


def _run_stage(entry: _StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    if _is_cpu_frame_stage(entry):
        return _run_cpu_frame_stage(entry, payload, metrics)
    return _run_tensor_frame_stage(entry, payload, metrics)


def _is_cpu_frame_stage(entry: _StepAlgorithm) -> bool:
    return entry.step.algorithm_type == "frame_filter_chain"


def _run_cpu_frame_stage(entry: _StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    process_numpy = getattr(entry.algorithm, "process_numpy", None)
    if not callable(process_numpy):
        raise RuntimeError(f"CPU frame stage '{entry.step.algorithm_type}' does not implement process_numpy().")
    frame = payload.ensure_numpy(metrics)
    return FramePayload.from_numpy(process_numpy(frame))


def _run_tensor_frame_stage(entry: _StepAlgorithm, payload: FramePayload, metrics: PipelineMetrics) -> FramePayload:
    tensor = payload.ensure_tensor(entry.backend, metrics)
    processed = entry.algorithm.process_frame(tensor)
    return FramePayload.from_tensor(processed, entry.backend)


def _emit_encoded_payload(
    *,
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    output_index: int,
    payload: FramePayload,
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    frame = payload.ensure_numpy(metrics)
    _queue_put(
        encode_queue,
        EncodedFrame(output_index=output_index, frame=frame),
        stop_event,
    )
    metrics.set_queue_depth("encode", encode_queue.qsize())


def _drain_decoded(
    decode_queue: queue.Queue[DecodedFrame | object],
    stop_event: threading.Event,
) -> Iterator[DecodedFrame]:
    """Yield ``DecodedFrame`` items until stop_event fires or ``_DECODE_END`` is seen.

    Phase D.6.3 — 把两条 processor 主循环里相同的 "wait / sentinel /
    instance-check" 三连提到一个生成器。调用方只关心"下一个真实帧"。
    """
    while not stop_event.is_set():
        item = _queue_get(decode_queue, stop_event)
        if item is None:
            continue
        if item is _DECODE_END:
            return
        if isinstance(item, DecodedFrame):
            yield item


def _apply_pre_steps(
    *,
    pre_algorithms: list[_StepAlgorithm],
    progress_callbacks: list[Callable[[int, int], None]],
    item: DecodedFrame,
    source_frames: int,
    metrics: PipelineMetrics,
) -> FramePayload:
    """Run every pre-step algorithm on a decoded frame, reporting per-step progress.

    Progress denominator is fixed at ``max(source_frames, 1)`` so the NDJSON
    percent always reflects source-frame coverage regardless of pipeline shape.
    """
    return _apply_stage_chain(
        algorithms=pre_algorithms,
        progress_callbacks=progress_callbacks,
        payload=FramePayload.from_numpy(item.frame),
        progress_current=item.source_index + 1,
        progress_total=max(source_frames, 1),
        metrics=metrics,
    )


def _emit_stream_end(
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    source_frames: int,
    stop_event: threading.Event,
) -> None:
    """Tail of every processor stream — StreamEnd marker + encoder sentinel."""
    _queue_put(encode_queue, StreamEnd(next_source_frame=source_frames), stop_event)
    _queue_put(encode_queue, _ENCODE_END, stop_event)
