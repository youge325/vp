"""Sequence processor stream loop."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from app.planning import StagePlan
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor_algorithms import PipelineAlgorithms, ordered_algorithm_entries
from app.processing.streaming.processor_stage_execution import run_sequence_pipeline
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
)


def process_sequence_stream(
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
    """Run a pipeline containing at least one frame-sequence algorithm."""
    payloads = [FramePayload.from_numpy(item.frame) for item in drain_decoded(decode_queue, stop_event)]
    payloads = run_sequence_pipeline(
        entries=ordered_algorithm_entries(algorithms),
        payloads=payloads,
        progress_callbacks=progress_callbacks,
        metrics=metrics,
    )

    output_index = resume_output_frames
    for payload in payloads:
        emit_encoded_payload(
            encode_queue=encode_queue,
            output_index=output_index,
            payload=payload,
            stop_event=stop_event,
            metrics=metrics,
        )
        output_index += 1

    emit_stream_end(encode_queue, source_frames, stop_event)
    del stage_plan


__all__ = ["process_sequence_stream"]
