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

import numpy as np

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.planning import ProcessingStep, StagePlan
from app.processing.streaming._tensor_chain import run_tensor_chain
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
    held: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames

    for item in _drain_decoded(decode_queue, stop_event):
        frame = _apply_pre_steps(
            pre_algorithms=algorithms.pre,
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

    # Phase 11 — 提前抽出 post 链路的 (backend, algorithm) 列表,供
    # ``run_tensor_chain`` 单 H2D + 单 D2H 路径复用;所有 post step 在
    # _initialize_algorithms 中绑定的是同一个 ``shared_backend``,所以
    # 取第 0 个就代表整条链。
    post_steps = algorithms.post
    post_algorithm_objs = [entry.algorithm for entry in post_steps]
    post_backend = post_steps[0].backend if post_steps else None
    total_output_frames_denominator = max(stage_plan.total_output_frames, 1)

    # Phase 11 — ``previous`` 多带一个 prev_tensor 槽位,下一轮直接复用上一轮的
    # ``current_tensor``,把每对相邻帧的 H2D 拷贝从 2 次降到 1 次(首帧 lazy,
    # 末帧无下一轮所以不会浪费)。第三项允许 ``None``:首帧入时还没用上,
    # 真正进入插值循环时再 lazy 转换。
    previous: tuple[int, np.ndarray, Any | None] | None = None
    output_index = resume_output_frames
    total_pairs = max(source_frames - 1, 1)

    for item in _drain_decoded(decode_queue, stop_event):
        current_frame = _apply_pre_steps(
            pre_algorithms=algorithms.pre,
            progress_callbacks=progress_callbacks,
            item=item,
            source_frames=source_frames,
            metrics=metrics,
        )

        if previous is None:
            previous = (item.source_index, current_frame, None)
            continue

        prev_source_index, prev_frame, prev_tensor_cached = previous
        interpolation_callback(prev_source_index + 1, total_pairs)

        group_frames = [prev_frame]
        with metrics.timed("interpolate"):
            # Phase 11 — prev_tensor 复用上一轮的 current_tensor;仅首对帧需
            # 要 lazy H2D(``prev_tensor_cached is None`` 时)。
            if prev_tensor_cached is None:
                prev_tensor = interpolation_backend.numpy_to_tensor(prev_frame)
            else:
                prev_tensor = prev_tensor_cached
            current_tensor = interpolation_backend.numpy_to_tensor(current_frame)
            for mid_index in range(1, multi):
                timestep = mid_index / multi
                mid_tensor = interpolation_algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
                group_frames.append(interpolation_backend.tensor_to_numpy(mid_tensor))

        for frame in group_frames:
            processed_output = _run_post_chain(
                post_backend=post_backend,
                post_algorithm_objs=post_algorithm_objs,
                post_callbacks=post_callbacks,
                frame=frame,
                output_index=output_index,
                total_output_frames_denominator=total_output_frames_denominator,
            )
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
        previous = (item.source_index, current_frame, current_tensor)

    if previous is not None:
        final_frame = previous[1]
        final_output = _run_post_chain(
            post_backend=post_backend,
            post_algorithm_objs=post_algorithm_objs,
            post_callbacks=post_callbacks,
            frame=final_frame,
            output_index=output_index,
            total_output_frames_denominator=total_output_frames_denominator,
        )
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=final_output),
            stop_event,
        )
        metrics.set_queue_depth("encode", encode_queue.qsize())
        output_index += 1

    _emit_stream_end(encode_queue, source_frames, stop_event)


def _run_post_chain(
    *,
    post_backend: Any,
    post_algorithm_objs: list[Any],
    post_callbacks: list[Callable[[int, int], None]],
    frame: np.ndarray,
    output_index: int,
    total_output_frames_denominator: int,
) -> np.ndarray:
    """Apply the post chain to a single frame with single H2D + single D2H.

    Phase 11 — 等价语义改写原 line 236-240 / 256-263 的内联 post 循环。

    - 空 post(``post_algorithm_objs == []`` / ``post_backend is None``):
      ``run_tensor_chain`` 直接 return frame,我们也不调任何 callback
      (原代码同样不进 for 循环,无 callback 触发)。
    - 单步 post:等价于 1 次 H2D + 1 次 D2H,与 ``_run_single_frame_algorithm`` 同。
    - 多步 post:中间无 numpy↔tensor 转换,GPU 上一路流转。

    callback 在每步 ``process_frame`` 完成后立即调用,保留原"逐 step emit
    NDJSON progress"的节奏(reporter 节流会自然合并近距离的同 percent 调用,
    所以 NDJSON 帧密度与原实现近似)。
    """
    if post_backend is None or not post_algorithm_objs:
        return frame

    def emit_step(step_index: int) -> None:
        post_callbacks[step_index](output_index + 1, total_output_frames_denominator)

    return run_tensor_chain(
        post_backend,
        post_algorithm_objs,
        frame,
        step_callback=emit_step,
    )


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
    pre_algorithms: list[_StepAlgorithm],
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
        for step_index, entry in enumerate(pre_algorithms):
            frame = _run_single_frame_algorithm(entry.backend, entry.algorithm, frame)
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
