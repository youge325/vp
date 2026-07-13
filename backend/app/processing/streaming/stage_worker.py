"""Single-stage rawvideo worker runtime.

The production ``process`` command uses this module through the internal
``stage-worker`` CLI subcommand so every algorithm stage can live in its own
Python process.  Tests call :func:`run_stage_worker_stream` directly with
in-memory streams and fake algorithms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, BinaryIO, Callable

from app.algorithms.tensor_backend import get_tensor_backend
from app.processing.streaming import stage_worker_progress
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_execution import (
    run_interpolation_stage,
    run_sequence_stage,
    run_single_frame_stage,
)
from app.processing.streaming.stage_worker_factory import (
    create_algorithm,
    create_backend,
)
from app.processing.streaming.stage_runtime import (
    algorithm_needs_pairs,
    algorithm_needs_sequence,
)

if TYPE_CHECKING:
    from app.planning import ProcessingStep
    from app.processing.streaming.stage_worker_config import StageWorkerConfig
    from app.processing.streaming.stage_worker_progress import EventSink


def run_stage_worker_stream(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    *,
    algorithm_factory: Callable[[ProcessingStep, Any], Any] | None = None,
    backend_factory: Callable[[str], Any] | None = None,
    event_sink: EventSink | None = None,
) -> None:
    """Run exactly one configured stage over rawvideo streams."""
    sink = event_sink or (lambda _event: None)
    backend = create_backend(config, backend_factory or get_tensor_backend)
    algorithm = (algorithm_factory or create_algorithm)(config.stage, backend)
    metrics = PipelineMetrics()

    if algorithm_needs_sequence(algorithm):
        run_sequence_stage(
            config,
            input_stream,
            output_stream,
            algorithm,
            sink,
            heartbeat_seconds=stage_worker_progress.SEQUENCE_STAGE_HEARTBEAT_SECONDS,
        )
    elif algorithm_needs_pairs(algorithm):
        run_interpolation_stage(config, input_stream, output_stream, backend, algorithm, sink, metrics)
    else:
        run_single_frame_stage(config, input_stream, output_stream, backend, algorithm, sink, metrics)

    flush = getattr(output_stream, "flush", None)
    if callable(flush):
        flush()


__all__ = ["run_stage_worker_stream"]
