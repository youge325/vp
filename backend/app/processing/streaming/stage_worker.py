"""Single-stage rawvideo worker runtime.

The production ``process`` command uses this module through the internal
``stage-worker`` CLI subcommand so every algorithm stage can live in its own
Python process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from app.algorithms.interfaces import (
    FramePairAlgorithm,
    FrameSequenceAlgorithm,
    NumpyFrameAlgorithm,
    SingleFrameAlgorithm,
)
from app.generated.stage_worker_contracts import StageWorkerConfig
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
from app.processing.streaming.stage_worker_config import processing_step_from_config

if TYPE_CHECKING:
    from app.processing.streaming.stage_worker_progress import EventSink


def run_stage_worker_stream(
    config: StageWorkerConfig,
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    *,
    event_sink: EventSink,
    model_root: str,
) -> None:
    """Run exactly one configured stage over rawvideo streams."""
    step = processing_step_from_config(config)
    backend = create_backend(config, step)
    algorithm = create_algorithm(step, backend, model_root=model_root)
    metrics = PipelineMetrics()

    if step.execution_mode == "sequence":
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
    elif step.execution_mode == "pair":
        if not isinstance(algorithm, FramePairAlgorithm):
            raise RuntimeError("Pair stage factory returned an incompatible algorithm.")
        if backend is None:
            raise RuntimeError("Frame interpolation stage requires a tensor backend.")
        run_interpolation_stage(config, step, input_stream, output_stream, backend, algorithm, event_sink, metrics)
    else:
        expected_port = NumpyFrameAlgorithm if step.algorithm_type == "frame_filter_chain" else SingleFrameAlgorithm
        if not isinstance(algorithm, expected_port):
            raise RuntimeError("Single-frame stage factory returned an incompatible algorithm.")
        run_single_frame_stage(config, step, input_stream, output_stream, backend, algorithm, event_sink, metrics)

    output_stream.flush()


__all__ = ["run_stage_worker_stream"]
