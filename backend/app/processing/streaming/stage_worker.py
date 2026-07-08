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
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_io import (
    RawVideoFrameError,
    read_rgb_frame,
    write_rgb_frame,
)
from app.processing.streaming.stage_worker_execution import (
    run_interpolation_stage,
    run_sequence_stage,
    run_single_frame_stage,
)
from app.processing.streaming.stage_worker_runtime import (
    STAGE_EVENT_PREFIX,
    AlgorithmFactory,
    AlgorithmFactoryFn,
    BackendFactoryFn,
    EventSink,
    SEQUENCE_STAGE_HEARTBEAT_SECONDS,
    create_algorithm,
    create_backend,
    emit_stage_event,
)
from app.processing.streaming.stage_runtime import (
    algorithm_needs_pairs,
    algorithm_needs_sequence,
)

_run_interpolation_stage = run_interpolation_stage
_run_sequence_stage = run_sequence_stage
_run_single_frame_stage = run_single_frame_stage


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
        written = _run_sequence_stage(
            config,
            input_stream,
            output_stream,
            algorithm,
            sink,
            metrics,
            heartbeat_seconds=SEQUENCE_STAGE_HEARTBEAT_SECONDS,
        )
    elif algorithm_needs_pairs(algorithm):
        written = _run_interpolation_stage(config, input_stream, output_stream, backend, algorithm, sink, metrics)
    else:
        written = _run_single_frame_stage(config, input_stream, output_stream, backend, algorithm, sink, metrics)

    flush = getattr(output_stream, "flush", None)
    if callable(flush):
        flush()
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
