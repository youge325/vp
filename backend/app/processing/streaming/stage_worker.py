"""Single-stage rawvideo worker runtime.

The production ``process`` command uses this module through the internal
``stage-worker`` CLI subcommand so every algorithm stage can live in its own
Python process.  Tests call :func:`run_stage_worker_stream` directly with
in-memory streams and fake algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, BinaryIO, Mapping

from app.algorithms.tensor_backend import get_tensor_backend
from app.planning import ProcessingStep, normalize_processing_step
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_io import (
    RawVideoFrameError,
    read_declared_frames,
    read_rgb_frame,
    write_rgb_frame,
)
from app.processing.streaming.stage_worker_runtime import (
    STAGE_EVENT_PREFIX,
    AlgorithmFactory,
    AlgorithmFactoryFn,
    BackendFactoryFn,
    EventSink,
    SEQUENCE_STAGE_HEARTBEAT_SECONDS,
    StageProgressState,
    create_algorithm,
    create_backend,
    emit_stage_event,
    progress_event,
    start_sequence_stage_heartbeat,
)
from app.processing.streaming.stage_runtime import (
    StepAlgorithm,
    algorithm_needs_pairs,
    algorithm_needs_sequence,
    is_cpu_frame_stage,
    run_stage,
)


@dataclass(frozen=True, slots=True)
class StageWorkerConfig:
    """JSON-serialisable configuration for one isolated algorithm stage."""

    stage: ProcessingStep
    stage_index: int
    stage_total: int
    stage_name: str
    input_width: int
    input_height: int
    output_width: int
    output_height: int
    input_frame_count: int
    tensor_backend_name: str
    output_frame_count: int | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StageWorkerConfig":
        def value(camel: str, snake: str) -> Any:
            return payload[camel] if camel in payload else payload[snake]

        return cls(
            stage=normalize_processing_step(value("stage", "stage")),
            stage_index=int(value("stageIndex", "stage_index")),
            stage_total=int(value("stageTotal", "stage_total")),
            stage_name=str(value("stageName", "stage_name")),
            input_width=int(value("inputWidth", "input_width")),
            input_height=int(value("inputHeight", "input_height")),
            output_width=int(value("outputWidth", "output_width")),
            output_height=int(value("outputHeight", "output_height")),
            input_frame_count=int(value("inputFrameCount", "input_frame_count")),
            tensor_backend_name=str(value("tensorBackendName", "tensor_backend_name")),
            output_frame_count=int(payload.get("outputFrameCount") or payload.get("output_frame_count") or 0) or None,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "StageWorkerConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise ValueError("Stage worker config must be a JSON object.")
        return cls.from_mapping(payload)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "stage": self.stage.to_jsonable(),
            "stageIndex": self.stage_index,
            "stageTotal": self.stage_total,
            "stageName": self.stage_name,
            "inputWidth": self.input_width,
            "inputHeight": self.input_height,
            "outputWidth": self.output_width,
            "outputHeight": self.output_height,
            "inputFrameCount": self.input_frame_count,
            "tensorBackendName": self.tensor_backend_name,
            "outputFrameCount": self.output_frame_count,
        }


def run_stage_worker_stream(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    *,
    algorithm_factory: AlgorithmFactoryFn | None = None,
    backend_factory: BackendFactoryFn | None = None,
    event_sink: EventSink | None = None,
) -> int:
    """Run exactly one configured stage over rawvideo streams.

    Returns the number of frames written to ``output_stream``.
    """
    sink = event_sink or (lambda _event: None)
    backend = create_backend(config, backend_factory or get_tensor_backend)
    algorithm = (algorithm_factory or create_algorithm)(config.stage, backend)
    metrics = PipelineMetrics()

    if algorithm_needs_sequence(algorithm):
        written = _run_sequence_stage(config, input_stream, output_stream, algorithm, sink, metrics)
    elif algorithm_needs_pairs(algorithm):
        written = _run_interpolation_stage(config, input_stream, output_stream, backend, algorithm, sink, metrics)
    else:
        written = _run_single_frame_stage(config, input_stream, output_stream, backend, algorithm, sink, metrics)

    flush = getattr(output_stream, "flush", None)
    if callable(flush):
        flush()
    return written


def _run_sequence_stage(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    algorithm: Any,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> int:
    del metrics
    frames = read_declared_frames(config, input_stream)
    total = max(int(config.output_frame_count or config.input_frame_count or len(frames)), 1)
    progress_state = StageProgressState()
    event_sink(progress_event(config, 0, total, force=True))
    stop_heartbeat, heartbeat_thread = start_sequence_stage_heartbeat(
        config,
        event_sink,
        total,
        progress_state,
        heartbeat_seconds=SEQUENCE_STAGE_HEARTBEAT_SECONDS,
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


def _run_interpolation_stage(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    backend: Any,
    algorithm: Any,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> int:
    frames = read_declared_frames(config, input_stream)
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


def _run_single_frame_stage(
    config: StageWorkerConfig,
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


__all__ = [
    "AlgorithmFactory",
    "RawVideoFrameError",
    "STAGE_EVENT_PREFIX",
    "StageWorkerConfig",
    "emit_stage_event",
    "read_rgb_frame",
    "run_stage_worker_stream",
    "write_rgb_frame",
]
