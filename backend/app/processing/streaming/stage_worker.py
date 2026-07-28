"""Single-stage rawvideo worker runtime.

The production ``process`` command uses this module through the internal
``stage-worker`` CLI subcommand so every algorithm stage can live in its own
Python process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from app.algorithms.interfaces import FramePairAlgorithm, FrameSequenceAlgorithm, SingleFrameAlgorithm
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

    if config.stage.execution_mode == "sequence":
        if not isinstance(algorithm, FrameSequenceAlgorithm):
            raise RuntimeError("Sequence stage factory returned an incompatible algorithm.")
        run_sequence_stage(
            config,
            input_stream,
            output_stream,
            algorithm,
            event_sink,
            heartbeat_seconds=stage_worker_progress.SEQUENCE_STAGE_HEARTBEAT_SECONDS,
        )
    elif config.stage.execution_mode == "pair":
        if not isinstance(algorithm, FramePairAlgorithm):
            raise RuntimeError("Pair stage factory returned an incompatible algorithm.")
        if backend is None:
            raise RuntimeError("Frame interpolation stage requires a tensor backend.")
        run_interpolation_stage(config, input_stream, output_stream, backend, algorithm, event_sink, metrics)
    else:
        if not isinstance(algorithm, SingleFrameAlgorithm):
            raise RuntimeError("Single-frame stage factory returned an incompatible algorithm.")
        run_single_frame_stage(config, input_stream, output_stream, backend, algorithm, event_sink, metrics)

    output_stream.flush()


__all__ = ["run_stage_worker_stream"]
