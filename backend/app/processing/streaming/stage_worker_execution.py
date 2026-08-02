"""Execution loops for isolated rawvideo stage workers."""

from __future__ import annotations

from typing import BinaryIO

import numpy as np

from app.algorithms.interfaces import (
    FramePairAlgorithm,
    FrameSequenceAlgorithm,
    NumpyFrameAlgorithm,
    SingleFrameAlgorithm,
)
from app.algorithms.tensor_backend import ITensorBackend
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_runtime import StepAlgorithm, run_stage
from app.processing.streaming.stage_worker_io import (
    RawVideoFrameError,
    read_rgb_frame,
    write_rgb_frame,
)
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.stage_worker_progress import (
    EventSink,
    SEQUENCE_STAGE_HEARTBEAT_SECONDS,
    StageProgressState,
    progress_event,
    start_sequence_stage_heartbeat,
)


def run_sequence_stage(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    algorithm: FrameSequenceAlgorithm,
    event_sink: EventSink,
    *,
    heartbeat_seconds: float = SEQUENCE_STAGE_HEARTBEAT_SECONDS,
) -> None:
    frames = _read_declared_frames(config, input_stream)
    total = max(config.output_frame_count, 1)
    progress_state = StageProgressState()
    event_sink(progress_event(config, 0, total, force=True))
    stop_heartbeat, heartbeat_thread = start_sequence_stage_heartbeat(
        config,
        event_sink,
        total,
        progress_state,
        heartbeat_seconds=heartbeat_seconds,
    )

    def sequence_progress(current: int, _progress_total: int | None = None) -> None:
        logical_current = min(max(int(current) - config.output_frame_offset, 0), config.output_frame_count)
        progress_state.current = max(progress_state.current, logical_current)
        resolved_total = total
        progress_state.total = resolved_total
        event_sink(
            progress_event(
                config,
                progress_state.current,
                resolved_total,
                force=progress_state.current >= resolved_total,
            )
        )

    try:
        output_frames = algorithm.process_frame_sequence(frames, progress_callback=sequence_progress)
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)
    if len(output_frames) != config.input_frame_count:
        raise RawVideoFrameError(
            f"Stage worker output frame count mismatch: expected {config.input_frame_count}, got {len(output_frames)}."
        )
    output_start = config.output_frame_offset
    output_end = output_start + config.output_frame_count
    if output_end > len(output_frames):
        raise RawVideoFrameError(
            "Stage worker output slice exceeds algorithm output: "
            f"offset {output_start}, count {config.output_frame_count}, available {len(output_frames)}."
        )
    output_frames = output_frames[output_start:output_end]
    _require_output_frame_count(config, len(output_frames))
    total = max(config.output_frame_count, 1)
    emit_write_progress = progress_state.current <= 0
    for index, frame in enumerate(output_frames, start=1):
        write_rgb_frame(output_stream, frame, width=config.output_width, height=config.output_height)
        if emit_write_progress:
            event_sink(progress_event(config, index, total, force=index >= total))
    if not emit_write_progress:
        event_sink(progress_event(config, total, total, force=True))


def run_interpolation_stage(
    config: StageWorkerConfig,
    step: ProcessingStep,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    backend: ITensorBackend,
    algorithm: FramePairAlgorithm,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> None:
    frames = _read_declared_frames(config, input_stream)
    multi = int(step.algorithm_kwargs["multi"])
    projected_output_count = 0 if not frames else 1 + (len(frames) - 1) * multi
    _require_output_frame_count(config, projected_output_count)
    if not frames:
        return
    if len(frames) == 1:
        write_rgb_frame(output_stream, frames[0], width=config.output_width, height=config.output_height)
        event_sink(progress_event(config, 1, 1))
        return

    total_pairs = len(frames) - 1
    previous_payload = FramePayload.from_numpy(frames[0])
    for pair_index, current_frame in enumerate(frames[1:], start=1):
        current_payload = FramePayload.from_numpy(current_frame)
        prev_tensor = previous_payload.ensure_tensor(backend, metrics)
        current_tensor = current_payload.ensure_tensor(backend, metrics)

        write_rgb_frame(
            output_stream,
            previous_payload.ensure_numpy(metrics),
            width=config.output_width,
            height=config.output_height,
        )
        for mid_index in range(1, multi):
            timestep = mid_index / multi
            mid_tensor = algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
            mid_frame = FramePayload.from_tensor(mid_tensor, backend).ensure_numpy(metrics)
            write_rgb_frame(output_stream, mid_frame, width=config.output_width, height=config.output_height)
        event_sink(progress_event(config, pair_index, total_pairs))
        previous_payload = current_payload

    write_rgb_frame(
        output_stream,
        previous_payload.ensure_numpy(metrics),
        width=config.output_width,
        height=config.output_height,
    )


def run_single_frame_stage(
    config: StageWorkerConfig,
    step: ProcessingStep,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    backend: ITensorBackend | None,
    algorithm: SingleFrameAlgorithm | NumpyFrameAlgorithm,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> None:
    _require_output_frame_count(config, config.input_frame_count)
    entry = StepAlgorithm(step=step, backend=backend, algorithm=algorithm)
    total = max(config.input_frame_count, 1)
    for index in range(config.input_frame_count):
        frame = read_rgb_frame(input_stream, width=config.input_width, height=config.input_height)
        if frame is None:
            raise RawVideoFrameError(
                f"rawvideo stream ended before {config.input_frame_count} declared input frames were read."
            )
        payload = run_stage(
            entry,
            FramePayload.from_numpy(frame),
            metrics,
        )
        write_rgb_frame(
            output_stream, payload.ensure_numpy(metrics), width=config.output_width, height=config.output_height
        )
        event_sink(progress_event(config, index + 1, total))


def _read_declared_frames(config: StageWorkerConfig, input_stream: BinaryIO) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for _ in range(max(config.input_frame_count, 0)):
        frame = read_rgb_frame(input_stream, width=config.input_width, height=config.input_height)
        if frame is None:
            raise RawVideoFrameError(
                f"rawvideo stream ended before {config.input_frame_count} declared input frames were read."
            )
        frames.append(frame)
    return frames


def _require_output_frame_count(config: StageWorkerConfig, actual: int) -> None:
    if actual != config.output_frame_count:
        raise RawVideoFrameError(
            f"Stage worker output frame count mismatch: expected {config.output_frame_count}, got {actual}."
        )


__all__ = [
    "run_interpolation_stage",
    "run_sequence_stage",
    "run_single_frame_stage",
]
