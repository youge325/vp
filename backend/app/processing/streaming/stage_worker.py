"""Single-stage rawvideo worker runtime.

The production ``process`` command uses this module through the internal
``stage-worker`` CLI subcommand so every algorithm stage can live in its own
Python process.  Tests call :func:`run_stage_worker_stream` directly with
in-memory streams and fake algorithms.
"""

from __future__ import annotations

from typing import BinaryIO

from app.algorithms.tensor_backend import get_tensor_backend
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_config import StageWorkerConfig
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
from app.processing.streaming.stage_worker_factory import (
    AlgorithmFactory,
    AlgorithmFactoryFn,
    BackendFactoryFn,
    create_algorithm,
    create_backend,
)
from app.processing.streaming.stage_worker_progress import (
    EventSink,
    SEQUENCE_STAGE_HEARTBEAT_SECONDS,
    STAGE_EVENT_PREFIX,
    emit_stage_event,
)
from app.processing.streaming.stage_runtime import (
    algorithm_needs_pairs,
    algorithm_needs_sequence,
)

_run_interpolation_stage = run_interpolation_stage
_run_sequence_stage = run_sequence_stage
_run_single_frame_stage = run_single_frame_stage


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
