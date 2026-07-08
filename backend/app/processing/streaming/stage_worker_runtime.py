"""Runtime helper rules for isolated stage workers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sys
import threading
from typing import Any, Callable

from app.algorithms.factory import AlgorithmFactory
from app.planning import ProcessingStep
from app.processing.streaming.stage_rules import algorithm_kwargs_for_create

STAGE_EVENT_PREFIX = "VP_STAGE_EVENT "
SEQUENCE_STAGE_HEARTBEAT_SECONDS = 30.0

EventSink = Callable[[dict[str, Any]], None]
AlgorithmFactoryFn = Callable[[ProcessingStep, Any], Any]
BackendFactoryFn = Callable[[str], Any]


@dataclass(slots=True)
class StageProgressState:
    current: int = 0
    total: int = 1


def emit_stage_event(event: dict[str, Any], *, stream: Any = None) -> None:
    """Emit one worker event to stderr with a parseable prefix."""
    target = stream if stream is not None else sys.stderr
    print(f"{STAGE_EVENT_PREFIX}{json.dumps(event, ensure_ascii=False)}", file=target, flush=True)


def create_backend(config: Any, backend_factory: BackendFactoryFn) -> Any:
    if config.stage.algorithm_type == "frame_filter_chain":
        return None
    return backend_factory(config.tensor_backend_name)


def create_algorithm(stage: ProcessingStep, backend: Any) -> Any:
    if stage.algorithm_type == "frame_filter_chain":
        from app.processing.frame_filters import FrameFilterChainAlgorithm

        return FrameFilterChainAlgorithm(tensor_backend=None, **stage.algorithm_kwargs)

    register_single_algorithm(stage.algorithm_type)
    return AlgorithmFactory.create(
        algorithm_type=stage.algorithm_type,
        tensor_backend=backend,
        tensor_backend_name=backend_name(backend),
        **algorithm_kwargs_for_create(stage),
    )


def register_single_algorithm(algorithm_type: str) -> None:
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


def backend_name(backend: Any) -> str:
    get_name = getattr(backend, "get_name", None)
    if callable(get_name):
        return str(get_name())
    return "numpy"


def progress_event(
    config: Any,
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


def start_sequence_stage_heartbeat(
    config: Any,
    event_sink: EventSink,
    total: int,
    progress_state: StageProgressState,
    *,
    heartbeat_seconds: float = SEQUENCE_STAGE_HEARTBEAT_SECONDS,
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    progress_state.total = max(int(total), 1)

    def run() -> None:
        while not stop_event.wait(max(float(heartbeat_seconds), 0.001)):
            event_sink(
                progress_event(
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


__all__ = [
    "AlgorithmFactory",
    "AlgorithmFactoryFn",
    "BackendFactoryFn",
    "EventSink",
    "SEQUENCE_STAGE_HEARTBEAT_SECONDS",
    "STAGE_EVENT_PREFIX",
    "StageProgressState",
    "backend_name",
    "create_algorithm",
    "create_backend",
    "emit_stage_event",
    "progress_event",
    "register_single_algorithm",
    "start_sequence_stage_heartbeat",
]
