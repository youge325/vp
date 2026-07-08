"""Single-frame processor stream loop."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from app.planning import StagePlan
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_algorithms import PipelineAlgorithms
from app.processing.streaming.processor_stage_execution import apply_pre_steps
from app.processing.streaming.processor_stream_io import (
    drain_decoded,
    emit_encoded_payload,
    emit_stream_end,
)
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _queue_put,
)


def process_single_frame_stream(
    *,
    stage_plan: StagePlan,
    algorithms: PipelineAlgorithms,
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

    for item in drain_decoded(decode_queue, stop_event):
        payload = apply_pre_steps(
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
        emit_encoded_payload(
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
        emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=held[1],
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1

    emit_stream_end(encode_queue, source_frames, stop_event)
    del stage_plan


__all__ = ["process_single_frame_stream"]
