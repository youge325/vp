"""Stage-worker stderr event parsing and progress forwarding."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from collections import deque
from typing import Any, Protocol, Sequence

from app.errors import ProcessError, TaskErrorCode, error_code_to_wire
from app.protocol.process_markers import TENSORRT_LOG_PREFIX as _TENSORRT_LOG_PREFIX
from app.processing.streaming.stage_worker_progress import STAGE_EVENT_PREFIX, StageProgressCallback
from app.processing.streaming.worker_plans import StageWorkerPlan


class _WorkerEventHandle(Protocol):
    process: subprocess.Popen[bytes]
    plan: StageWorkerPlan
    stderr_tail: deque[str]


def _parse_stage_event_line(line: str) -> dict[str, Any] | None:
    """Parse a structured worker stderr line, ignoring ordinary stderr."""
    if not line.startswith(STAGE_EVENT_PREFIX):
        return None
    payload = line[len(STAGE_EVENT_PREFIX) :].strip()
    event = json.loads(payload)
    if not isinstance(event, dict):
        return None
    return event


def read_worker_stderr(
    handle: _WorkerEventHandle,
    progress_callbacks: Sequence[StageProgressCallback | None],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    stderr = handle.process.stderr
    if stderr is None:
        return
    for raw_line in iter(stderr.readline, b""):
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        event = _parse_stage_event_line(line)
        if event is None:
            handle.stderr_tail.append(line)
            if _TENSORRT_LOG_PREFIX in line:
                print(line, file=sys.stderr, flush=True)
            continue
        if event.get("type") == "progress":
            callback_index = int(event.get("stageIndex") or handle.plan.config.stage_index) - 1
            if 0 <= callback_index < len(progress_callbacks):
                callback = progress_callbacks[callback_index]
                if callback is None:
                    continue
                try:
                    callback(
                        int(event.get("current") or 0),
                        int(event.get("total") or 1),
                        force=bool(event.get("force") or False),
                        heartbeat=bool(event.get("heartbeat") or False),
                    )
                except BaseException as exc:  # pragma: no cover - defensive thread boundary
                    stop_event.set()
                    error_queue.put(exc)
            continue
        if event.get("type") == "error":
            stop_event.set()
            error_queue.put(
                ProcessError(
                    error_code_to_wire(event.get("code") or TaskErrorCode.PROCESS_FAILED.value),
                    str(event.get("message") or "Stage worker failed."),
                    details=dict(event.get("details") or {}),
                )
            )


__all__ = ["read_worker_stderr"]
