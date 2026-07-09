"""Execution loops for isolated rawvideo stage workers."""

from __future__ import annotations

from typing import Any, BinaryIO

from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_runtime import StepAlgorithm, is_cpu_frame_stage, run_stage
from app.processing.streaming.stage_worker_io import (
    RawVideoFrameError,
    read_rgb_frame,
    write_rgb_frame,
)
from app.processing.streaming.stage_worker_progress import (
    EventSink,
    SEQUENCE_STAGE_HEARTBEAT_SECONDS,
    StageProgressState,
    progress_event,
    start_sequence_stage_heartbeat,
)


def run_sequence_stage(
    config: Any,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    algorithm: Any,
    event_sink: EventSink,
    metrics: PipelineMetrics,
    *,
    heartbeat_seconds: float = SEQUENCE_STAGE_HEARTBEAT_SECONDS,
) -> int:
    del metrics
    frames = _read_declared_frames(config, input_stream)
    total = max(int(config.output_frame_count or config.input_frame_count or len(frames)), 1)
    progress_state = StageProgressState()
    event_sink(progress_event(config, 0, total, force=True))
    stop_heartbeat, heartbeat_thread = start_sequence_stage_heartbeat(
        config,
        event_sink,
        total,
        progress_state,
        heartbeat_seconds=heartbeat_seconds,
    )

    def sequence_progress(current: int, progress_total: int | None = None) -> None:
        progress_state.current = max(progress_state.current, max(int(current), 0))
        resolved_total = max(int(progress_total or total), 1)
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
    total = max(len(output_frames), 1)
    emit_write_progress = progress_state.current <= 0
    for index, frame in enumerate(output_frames, start=1):
        write_rgb_frame(output_stream, frame, width=config.output_width, height=config.output_height)
        if emit_write_progress:
            event_sink(progress_event(config, index, total, force=index >= total))
    if not emit_write_progress:
        event_sink(progress_event(config, total, total, force=True))
    return len(output_frames)


def run_interpolation_stage(
    config: Any,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    backend: Any,
    algorithm: Any,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> int:
    frames = _read_declared_frames(config, input_stream)
    if not frames:
        return 0
    if len(frames) == 1:
        write_rgb_frame(output_stream, frames[0], width=config.output_width, height=config.output_height)
        event_sink(progress_event(config, 1, 1))
        return 1

    multi = int(
        config.stage.algorithm_kwargs.get("multi") or getattr(algorithm, "get_interpolation_multi", lambda: 2)()
    )
    total_pairs = len(frames) - 1
    written = 0
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
        written += 1
        for mid_index in range(1, multi):
            timestep = mid_index / multi
            mid_tensor = algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
            mid_frame = FramePayload.from_tensor(mid_tensor, backend).ensure_numpy(metrics)
            write_rgb_frame(output_stream, mid_frame, width=config.output_width, height=config.output_height)
            written += 1
        event_sink(progress_event(config, pair_index, total_pairs))
        previous_payload = current_payload

    write_rgb_frame(
        output_stream,
        previous_payload.ensure_numpy(metrics),
        width=config.output_width,
        height=config.output_height,
    )
    return written + 1


def run_single_frame_stage(
    config: Any,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    backend: Any,
    algorithm: Any,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> int:
    entry = StepAlgorithm(step=config.stage, backend=backend, algorithm=algorithm)
    total = max(config.input_frame_count, 1)
    written = 0
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
            prefer_tensor=not is_cpu_frame_stage(entry),
        )
        write_rgb_frame(
            output_stream, payload.ensure_numpy(metrics), width=config.output_width, height=config.output_height
        )
        written += 1
        event_sink(progress_event(config, index + 1, total))
    return written


def _read_declared_frames(config: Any, input_stream: BinaryIO) -> list[Any]:
    frames: list[Any] = []
    for _index in range(max(config.input_frame_count, 0)):
        frame = read_rgb_frame(input_stream, width=config.input_width, height=config.input_height)
        if frame is None:
            raise RawVideoFrameError(
                f"rawvideo stream ended before {config.input_frame_count} declared input frames were read."
            )
        frames.append(frame)
    return frames


__all__ = [
    "run_interpolation_stage",
    "run_sequence_stage",
    "run_single_frame_stage",
]
