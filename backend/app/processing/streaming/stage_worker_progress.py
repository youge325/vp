"""Event and progress helpers for isolated stage workers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sys
import threading
from typing import Any, Callable

STAGE_EVENT_PREFIX = "VP_STAGE_EVENT "
SEQUENCE_STAGE_HEARTBEAT_SECONDS = 30.0

EventSink = Callable[[dict[str, Any]], None]


@dataclass(slots=True)
class StageProgressState:
    current: int = 0
    total: int = 1


def emit_stage_event(event: dict[str, Any], *, stream: Any = None) -> None:
    """Emit one worker event to stderr with a parseable prefix."""
    target = stream if stream is not None else sys.stderr
    print(f"{STAGE_EVENT_PREFIX}{json.dumps(event, ensure_ascii=False)}", file=target, flush=True)


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
    "EventSink",
    "SEQUENCE_STAGE_HEARTBEAT_SECONDS",
    "STAGE_EVENT_PREFIX",
    "StageProgressState",
    "emit_stage_event",
    "progress_event",
    "start_sequence_stage_heartbeat",
]
