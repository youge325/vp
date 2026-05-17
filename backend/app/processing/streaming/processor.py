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
from typing import Any, Callable, Iterator

import numpy as np

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.planning import StagePlan
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


def _initialize_algorithms(stage_plan: StagePlan, tensor_backend_name: str) -> dict[str, Any]:
    algorithms: dict[str, Any] = {
        "single": [],
        "post": [],
        "interpolation": None,
    }

    # Re-use a single backend instance across all algorithms in the pipeline.
    # This avoids redundant DLL registration and repeated ``import onnxruntime``
    # when multiple steps share the same tensor backend.
    shared_backend = get_tensor_backend(tensor_backend_name)

    for step in stage_plan.pre_steps:
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["single"].append((step, shared_backend, algorithm))

    if stage_plan.interpolation_step is not None:
        algorithm = AlgorithmFactory.create(
            algorithm_type=stage_plan.interpolation_step["algorithm_type"],
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **stage_plan.interpolation_step["algorithm_kwargs"],
        )
        algorithms["interpolation"] = (shared_backend, algorithm)

    for step in stage_plan.post_steps:
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=shared_backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["post"].append((step, shared_backend, algorithm))

    return algorithms


def _process_single_frame_stream(
    *,
    stage_plan: StagePlan,
    algorithms: dict[str, Any],
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    held: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames

    for item in _drain_decoded(decode_queue, stop_event):
        frame = _apply_pre_steps(
            pre_algorithms=algorithms["single"],
            progress_callbacks=progress_callbacks,
            item=item,
            source_frames=source_frames,
            metrics=metrics,
        )

        if held is None:
            held = (item.source_index, frame)
            continue

        _held_source_index, held_frame = held
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=held_frame),
            stop_event,
        )
        metrics.set_queue_depth("encode", encode_queue.qsize())
        output_index += 1
        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        held = (item.source_index, frame)

    if held is not None:
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=held[1]),
            stop_event,
        )
        metrics.set_queue_depth("encode", encode_queue.qsize())
        output_index += 1

    _emit_stream_end(encode_queue, source_frames, stop_event)
    del stage_plan


def _process_interpolated_stream(
    *,
    stage_plan: StagePlan,
    algorithms: dict[str, Any],
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
    interpolation_backend, interpolation_algorithm = algorithms["interpolation"]
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or 2)

    previous: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames
    total_pairs = max(source_frames - 1, 1)

    for item in _drain_decoded(decode_queue, stop_event):
        current_frame = _apply_pre_steps(
            pre_algorithms=algorithms["single"],
            progress_callbacks=progress_callbacks,
            item=item,
            source_frames=source_frames,
            metrics=metrics,
        )

        if previous is None:
            previous = (item.source_index, current_frame)
            continue

        prev_source_index, prev_frame = previous
        interpolation_callback(prev_source_index + 1, total_pairs)

        group_frames = [prev_frame]
        with metrics.timed("interpolate"):
            prev_tensor = interpolation_backend.numpy_to_tensor(prev_frame)
            current_tensor = interpolation_backend.numpy_to_tensor(current_frame)
            for mid_index in range(1, multi):
                timestep = mid_index / multi
                mid_tensor = interpolation_algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
                group_frames.append(interpolation_backend.tensor_to_numpy(mid_tensor))

        for frame in group_frames:
            processed_output = frame
            for callback_index, (_, backend, algorithm) in enumerate(algorithms["post"]):
                processed_output = _run_single_frame_algorithm(backend, algorithm, processed_output)
                post_callbacks[callback_index](output_index + 1, max(stage_plan.total_output_frames, 1))
            _queue_put(
                encode_queue,
                EncodedFrame(output_index=output_index, frame=processed_output),
                stop_event,
            )
            metrics.set_queue_depth("encode", encode_queue.qsize())
            output_index += 1

        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        previous = (item.source_index, current_frame)

    if previous is not None:
        final_frame = previous[1]
        for callback_index, (_, backend, algorithm) in enumerate(algorithms["post"]):
            final_frame = _run_single_frame_algorithm(backend, algorithm, final_frame)
            post_callbacks[callback_index](output_index + 1, max(stage_plan.total_output_frames, 1))
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=final_frame),
            stop_event,
        )
        metrics.set_queue_depth("encode", encode_queue.qsize())
        output_index += 1

    _emit_stream_end(encode_queue, source_frames, stop_event)


def _run_single_frame_algorithm(backend: Any, algorithm: Any, frame: np.ndarray) -> np.ndarray:
    tensor = backend.numpy_to_tensor(frame)
    processed = algorithm.process_frame(tensor)
    return backend.tensor_to_numpy(processed)


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
    pre_algorithms: list[tuple[dict[str, Any], Any, Any]],
    progress_callbacks: list[Callable[[int, int], None]],
    item: DecodedFrame,
    source_frames: int,
    metrics: PipelineMetrics,
) -> np.ndarray:
    """Run every pre-step algorithm on a decoded frame, reporting per-step progress.

    Progress denominator is fixed at ``max(source_frames, 1)`` so the NDJSON
    percent always reflects source-frame coverage regardless of pipeline shape.
    """
    frame = item.frame
    with metrics.timed("process"):
        for step_index, (_, backend, algorithm) in enumerate(pre_algorithms):
            frame = _run_single_frame_algorithm(backend, algorithm, frame)
            progress_callbacks[step_index](item.source_index + 1, max(source_frames, 1))
    return frame


def _emit_stream_end(
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    source_frames: int,
    stop_event: threading.Event,
) -> None:
    """Tail of every processor stream — StreamEnd marker + encoder sentinel."""
    _queue_put(encode_queue, StreamEnd(next_source_frame=source_frames), stop_event)
    _queue_put(encode_queue, _ENCODE_END, stop_event)
