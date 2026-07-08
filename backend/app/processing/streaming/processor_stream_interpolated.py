"""Interpolated processor stream loop."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from app.planning import StagePlan
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_algorithms import PipelineAlgorithms
from app.processing.streaming.processor_stage_execution import apply_post_steps, apply_pre_steps
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


def process_interpolated_stream(
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

    for item in drain_decoded(decode_queue, stop_event):
        current_payload = apply_pre_steps(
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
                mid_tensor = interpolation_algorithm.process_frame_pair(
                    prev_tensor,
                    current_tensor,
                    timestep=timestep,
                )
                group_payloads.append(FramePayload.from_tensor(mid_tensor, interpolation_backend))

        for payload in group_payloads:
            processed_payload = apply_post_steps(
                post_algorithms=algorithms.post,
                post_callbacks=post_callbacks,
                payload=payload,
                output_index=output_index,
                total_output_frames_denominator=total_output_frames_denominator,
                metrics=metrics,
            )
            emit_encoded_payload(
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
        final_output = apply_post_steps(
            post_algorithms=algorithms.post,
            post_callbacks=post_callbacks,
            payload=final_payload,
            output_index=output_index,
            total_output_frames_denominator=total_output_frames_denominator,
            metrics=metrics,
        )
        emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=final_output,
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1

    emit_stream_end(encode_queue, source_frames, stop_event)


__all__ = ["process_interpolated_stream"]
