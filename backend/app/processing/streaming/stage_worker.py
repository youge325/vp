"""Single-stage rawvideo worker runtime.

The production ``process`` command uses this module through the internal
``stage-worker`` CLI subcommand so every algorithm stage can live in its own
Python process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

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
    from app.processing.streaming.stage_worker_config import StageWorkerConfig
    from app.processing.streaming.stage_worker_progress import EventSink


def run_stage_worker_stream(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    *,
    event_sink: EventSink,
) -> None:
    """Run exactly one configured stage over rawvideo streams."""
    backend = create_backend(config)
    algorithm = create_algorithm(config.stage, backend)
    metrics = PipelineMetrics()

    if algorithm_needs_sequence(algorithm):
        run_sequence_stage(
            config,
            input_stream,
            output_stream,
            algorithm,
            event_sink,
            heartbeat_seconds=stage_worker_progress.SEQUENCE_STAGE_HEARTBEAT_SECONDS,
        )
    elif algorithm_needs_pairs(algorithm):
        run_interpolation_stage(config, input_stream, output_stream, backend, algorithm, event_sink, metrics)
    else:
        run_single_frame_stage(config, input_stream, output_stream, backend, algorithm, event_sink, metrics)

    flush = getattr(output_stream, "flush", None)
    if callable(flush):
        flush()


__all__ = ["run_stage_worker_stream"]
