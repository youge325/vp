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
import sys
import threading
from typing import Any, BinaryIO, Callable, Mapping

import numpy as np

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.planning import ProcessingStep, normalize_processing_step
from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_rules import algorithm_kwargs_for_create
from app.processing.streaming.stage_runtime import (
    StepAlgorithm,
    algorithm_needs_pairs,
    algorithm_needs_sequence,
    is_cpu_frame_stage,
    run_stage,
)

STAGE_EVENT_PREFIX = "VP_STAGE_EVENT "
SEQUENCE_STAGE_HEARTBEAT_SECONDS = 30.0


class RawVideoFrameError(RuntimeError):
    """Raised when a rawvideo stream cannot yield a complete RGB frame."""


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


EventSink = Callable[[dict[str, Any]], None]
AlgorithmFactoryFn = Callable[[ProcessingStep, Any], Any]
BackendFactoryFn = Callable[[str], Any]


def emit_stage_event(event: dict[str, Any], *, stream: Any = None) -> None:
    """Emit one worker event to stderr with a parseable prefix."""
    target = stream if stream is not None else sys.stderr
    print(f"{STAGE_EVENT_PREFIX}{json.dumps(event, ensure_ascii=False)}", file=target, flush=True)


def read_rgb_frame(stream: BinaryIO, *, width: int, height: int) -> np.ndarray | None:
    """Read one ``rgb24`` frame from *stream*.

    Returns ``None`` only when EOF is reached before any frame bytes are read.
    Partial frames are corrupt rawvideo and raise ``RawVideoFrameError``.
    """
    frame_bytes = width * height * 3
    chunks: list[bytes] = []
    remaining = frame_bytes
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            if not chunks:
                return None
            raise RawVideoFrameError(
                f"partial rawvideo frame: expected {frame_bytes} bytes, got {frame_bytes - remaining}."
            )
        chunks.append(chunk)
        remaining -= len(chunk)

    return np.frombuffer(b"".join(chunks), dtype=np.uint8).reshape((height, width, 3)).copy()


def write_rgb_frame(stream: BinaryIO, frame: np.ndarray, *, width: int, height: int) -> None:
    """Write one HWC ``uint8`` RGB frame to *stream*."""
    if frame.shape != (height, width, 3):
        raise RawVideoFrameError(f"Frame shape mismatch: expected {(height, width, 3)}, got {frame.shape}.")
    if frame.dtype != np.uint8:
        frame = frame.astype(np.uint8)
    stream.write(np.ascontiguousarray(frame).tobytes())


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
    backend = _create_backend(config, backend_factory or get_tensor_backend)
    algorithm = (algorithm_factory or _create_algorithm)(config.stage, backend)
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


def _create_backend(config: StageWorkerConfig, backend_factory: BackendFactoryFn) -> Any:
    if config.stage.algorithm_type == "frame_filter_chain":
        return None
    return backend_factory(config.tensor_backend_name)


def _create_algorithm(stage: ProcessingStep, backend: Any) -> Any:
    if stage.algorithm_type == "frame_filter_chain":
        from app.processing.frame_filters import FrameFilterChainAlgorithm

        return FrameFilterChainAlgorithm(tensor_backend=None, **stage.algorithm_kwargs)

    _register_single_algorithm(stage.algorithm_type)
    return AlgorithmFactory.create(
        algorithm_type=stage.algorithm_type,
        tensor_backend=backend,
        tensor_backend_name=_backend_name(backend),
        **algorithm_kwargs_for_create(stage),
    )


def _register_single_algorithm(algorithm_type: str) -> None:
    if algorithm_type == "frame_interpolation":
        from app.processing.interpolation import FrameInterpolationAlgorithm

        AlgorithmFactory.register("frame_interpolation", FrameInterpolationAlgorithm)
        return
    if algorithm_type == "super_resolution":
        from app.processing.super_resolution import SuperResolutionAlgorithm

        AlgorithmFactory.register("super_resolution", SuperResolutionAlgorithm)
        return
    if algorithm_type == "anime_optimization":
        from app.processing.anime_optimization import AnimeOptimizationAlgorithm

        AlgorithmFactory.register("anime_optimization", AnimeOptimizationAlgorithm)
        return
    raise ValueError(f"Unsupported stage-worker algorithm type: {algorithm_type!r}")


def _backend_name(backend: Any) -> str:
    get_name = getattr(backend, "get_name", None)
    if callable(get_name):
        return str(get_name())
    return "numpy"


def _read_declared_frames(config: StageWorkerConfig, input_stream: BinaryIO) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for _index in range(max(config.input_frame_count, 0)):
        frame = read_rgb_frame(input_stream, width=config.input_width, height=config.input_height)
        if frame is None:
            raise RawVideoFrameError(
                f"rawvideo stream ended before {config.input_frame_count} declared input frames were read."
            )
        frames.append(frame)
    return frames


def _progress_event(
    config: StageWorkerConfig,
    current: int,
    total: int,
    *,
    heartbeat: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    event = {
        "type": "progress",
        "stageName": config.stage_name,
        "stageIndex": config.stage_index,
        "stageTotal": config.stage_total,
        "current": current,
        "total": total,
    }
    if heartbeat:
        event["heartbeat"] = True
    if force:
        event["force"] = True
    return event


def _run_sequence_stage(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    algorithm: Any,
    event_sink: EventSink,
    metrics: PipelineMetrics,
) -> int:
    del metrics
    frames = _read_declared_frames(config, input_stream)
    total = max(int(config.output_frame_count or config.input_frame_count or len(frames)), 1)
    progress_state = _StageProgressState()
    event_sink(_progress_event(config, 0, total, force=True))
    stop_heartbeat, heartbeat_thread = _start_sequence_stage_heartbeat(config, event_sink, total, progress_state)

    def sequence_progress(current: int, progress_total: int | None = None) -> None:
        progress_state.current = max(progress_state.current, max(int(current), 0))
        resolved_total = max(int(progress_total or total), 1)
        progress_state.total = resolved_total
        event_sink(
            _progress_event(
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
            event_sink(_progress_event(config, index, total, force=index >= total))
    if not emit_write_progress:
        event_sink(_progress_event(config, total, total, force=True))
    return len(output_frames)


@dataclass(slots=True)
class _StageProgressState:
    current: int = 0
    total: int = 1


def _start_sequence_stage_heartbeat(
    config: StageWorkerConfig,
    event_sink: EventSink,
    total: int,
    progress_state: _StageProgressState,
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    progress_state.total = max(int(total), 1)

    def run() -> None:
        while not stop_event.wait(max(float(SEQUENCE_STAGE_HEARTBEAT_SECONDS), 0.001)):
            event_sink(
                _progress_event(
                    config,
                    progress_state.current,
                    progress_state.total,
                    heartbeat=True,
                    force=True,
                )
            )

    thread = threading.Thread(target=run, name=f"vp-stage-worker-heartbeat-{config.stage_index}", daemon=True)
    thread.start()
    return stop_event, thread


def _run_interpolation_stage(
    config: StageWorkerConfig,
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
        event_sink(_progress_event(config, 1, 1))
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
        event_sink(_progress_event(config, pair_index, total_pairs))
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
        event_sink(_progress_event(config, index + 1, total))
    return written


__all__ = [
    "RawVideoFrameError",
    "STAGE_EVENT_PREFIX",
    "StageWorkerConfig",
    "emit_stage_event",
    "read_rgb_frame",
    "run_stage_worker_stream",
    "write_rgb_frame",
]
