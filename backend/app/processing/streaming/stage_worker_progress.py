"""Event and progress helpers for isolated stage workers."""

from __future__ import annotations

from dataclasses import dataclass
import sys
import threading
from typing import Any, Callable, Protocol

from app.generated.protocol_constants import STAGE_WORKER_EVENT_PREFIX
from app.generated.stage_worker_contracts import (
    StageWorkerConfig,
    StageWorkerErrorEvent,
    StageWorkerProgressEvent,
)
from app.protocol_encoding import encode_bounded_json_line

SEQUENCE_STAGE_HEARTBEAT_SECONDS = 30.0
_EVENT_WRITE_LOCK = threading.Lock()

_StageWorkerEvent = StageWorkerProgressEvent | StageWorkerErrorEvent
EventSink = Callable[[_StageWorkerEvent], None]


class StageProgressCallback(Protocol):
    def __call__(self, current: int, total: int, **metadata: Any) -> None: ...


@dataclass(slots=True)
class StageProgressState:
    current: int = 0
    total: int = 1


def emit_stage_event(event: _StageWorkerEvent) -> None:
    """Emit one worker event to stderr with a parseable prefix."""
    line = encode_bounded_json_line(
        event.model_dump(by_alias=True, mode="json"),
        prefix=STAGE_WORKER_EVENT_PREFIX,
    )
    with _EVENT_WRITE_LOCK:
        sys.stderr.write(line)
        sys.stderr.flush()


def progress_event(
    config: StageWorkerConfig,
    current: int,
    total: int,
    *,
    heartbeat: bool = False,
    force: bool = False,
) -> StageWorkerProgressEvent:
    return StageWorkerProgressEvent(
        type="progress",
        stage_name=config.stage_name,
        stage_index=config.stage_index,
        stage_total=config.stage_total,
        current=current,
        total=total,
        heartbeat=heartbeat,
        force=force,
    )


def start_sequence_stage_heartbeat(
    config: StageWorkerConfig,
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
    "EventSink",
    "SEQUENCE_STAGE_HEARTBEAT_SECONDS",
    "StageProgressCallback",
    "StageProgressState",
    "emit_stage_event",
    "progress_event",
    "start_sequence_stage_heartbeat",
]
