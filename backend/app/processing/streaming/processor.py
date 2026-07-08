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
from typing import Callable

from app.planning import StagePlan
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
    run_sequence_stage as _run_sequence_stage,
)
from app.processing.streaming.processor_streams import (
    drain_decoded as _drain_decoded,
    emit_encoded_payload as _emit_encoded_payload,
    emit_stream_end as _emit_stream_end,
    process_interpolated_stream as _process_interpolated_stream,
    process_sequence_stream as _process_sequence_stream,
    process_single_frame_stream as _process_single_frame_stream,
)
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _ENCODE_END,
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
    "_drain_decoded",
    "_emit_encoded_payload",
    "_emit_stream_end",
    "_process_interpolated_stream",
    "_process_sequence_stream",
    "_process_single_frame_stream",
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
