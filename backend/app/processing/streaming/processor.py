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
from typing import Callable, Iterator

from app.planning import StagePlan
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_algorithms import (
    PipelineAlgorithms as _PipelineAlgorithms,
    initialize_algorithms as _initialize_algorithms,
    ordered_algorithm_entries as _ordered_algorithm_entries,
    pipeline_needs_sequence as _pipeline_needs_sequence,
    resolve_processor_mode as _resolve_processor_mode,
)
from app.processing.streaming.processor_stage_execution import (
    apply_post_steps as _apply_post_steps,
    apply_pre_steps as _apply_pre_steps,
    apply_stage_chain as _apply_stage_chain,
    emit_stage_progress as _emit_stage_progress,
    run_interpolation_sequence_stage as _run_interpolation_sequence_stage,
    run_per_frame_sequence_stage as _run_per_frame_sequence_stage,
    run_sequence_pipeline as _run_sequence_pipeline,
    run_sequence_stage as _run_sequence_stage,
)
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
from app.processing.streaming.stage_runtime import (
    StepAlgorithm as _StepAlgorithm,
)

__all__ = [
    "_apply_post_steps",
    "_apply_pre_steps",
    "_apply_stage_chain",
    "_emit_stage_progress",
    "_PipelineAlgorithms",
    "_run_interpolation_sequence_stage",
    "_run_per_frame_sequence_stage",
    "_run_sequence_stage",
    "_StepAlgorithm",
    "_initialize_algorithms",
    "_ordered_algorithm_entries",
    "_pipeline_needs_sequence",
]


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
        processor_mode = _resolve_processor_mode(stage_plan, algorithms)

        if processor_mode == "sequence":
            _process_sequence_stream(
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
        elif processor_mode == "single_frame":
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
            has_tensor_stage_after_chain=False,
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
            has_tensor_stage_after_chain=True,
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


def _process_sequence_stream(
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
    """Run a pipeline containing at least one frame-sequence algorithm.

    PaddleGAN VSR models need temporal context, so this path gathers the
    current decoded span and applies the resolved stages in order. Pipelines
    without sequence stages continue to use the streaming per-frame paths.
    """
    payloads = [FramePayload.from_numpy(item.frame) for item in _drain_decoded(decode_queue, stop_event)]
    payloads = _run_sequence_pipeline(
        entries=_ordered_algorithm_entries(algorithms),
        payloads=payloads,
        progress_callbacks=progress_callbacks,
        metrics=metrics,
    )

    output_index = resume_output_frames
    for payload in payloads:
        _emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=payload,
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1

    _emit_stream_end(encode_queue, source_frames, stop_event)
    del stage_plan


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


def _emit_stream_end(
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    source_frames: int,
    stop_event: threading.Event,
) -> None:
    """Tail of every processor stream — StreamEnd marker + encoder sentinel."""
    _queue_put(encode_queue, StreamEnd(next_source_frame=source_frames), stop_event)
    _queue_put(encode_queue, _ENCODE_END, stop_event)
