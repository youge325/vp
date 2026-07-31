"""Stage-worker stderr event parsing and progress forwarding."""

from __future__ import annotations

import queue
import subprocess
import threading
from collections import deque
from typing import Protocol, Sequence

from pydantic import TypeAdapter, ValidationError

from app.errors import ProcessError, error_code_to_wire
from app.generated.protocol_constants import (
    NDJSON_LINE_LIMIT_BYTES,
    STAGE_WORKER_EVENT_PREFIX,
    STDERR_TAIL_LIMIT_BYTES,
)
from app.generated.stage_worker_contracts import StageWorkerConfig, StageWorkerErrorEvent, StageWorkerProgressEvent
from app.processing.streaming.runtime_ports import WorkerLogSink
from app.processing.streaming.error_channel import report_first_error
from app.processing.streaming.stage_worker_progress import StageProgressCallback


class _WorkerEventHandle(Protocol):
    process: subprocess.Popen[bytes]
    config: StageWorkerConfig
    stderr_tail: deque[str]


_EVENT_ADAPTER = TypeAdapter(StageWorkerProgressEvent | StageWorkerErrorEvent)


def _parse_stage_event_line(line: str) -> StageWorkerProgressEvent | StageWorkerErrorEvent | None:
    """Parse a structured worker stderr line, ignoring ordinary stderr."""
    if not line.startswith(STAGE_WORKER_EVENT_PREFIX):
        return None
    payload = line[len(STAGE_WORKER_EVENT_PREFIX) :].strip()
    return _EVENT_ADAPTER.validate_json(payload, by_alias=True, by_name=False)


def read_worker_stderr(
    handle: _WorkerEventHandle,
    progress_callbacks: Sequence[StageProgressCallback | None],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    worker_log_sink: WorkerLogSink,
) -> None:
    stderr = handle.process.stderr
    if stderr is None:
        return

    def read_line() -> bytes:
        try:
            return stderr.readline(NDJSON_LINE_LIMIT_BYTES + 1)
        except BaseException as exc:  # pragma: no cover - process pipe boundary
            report_first_error(error_queue, stop_event, exc)
            return b""

    while raw_line := read_line():
        if len(raw_line) > NDJSON_LINE_LIMIT_BYTES:
            while raw_line and not raw_line.endswith(b"\n"):
                raw_line = read_line()
            report_first_error(
                error_queue,
                stop_event,
                ValueError("Stage worker stderr line exceeds the protocol limit."),
            )
            continue
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = _parse_stage_event_line(line)
        except ValidationError as exc:
            report_first_error(error_queue, stop_event, exc)
            continue
        if event is None:
            _append_stderr_tail(handle.stderr_tail, line)
            try:
                worker_log_sink(line)
            except BaseException as exc:  # pragma: no cover - thread adapter boundary
                report_first_error(error_queue, stop_event, exc)
            continue
        if isinstance(event, StageWorkerProgressEvent):
            expected_identity = (
                handle.config.stage_name,
                handle.config.stage_index,
                handle.config.stage_total,
            )
            actual_identity = (event.stage_name, event.stage_index, event.stage_total)
            if actual_identity != expected_identity:
                report_first_error(
                    error_queue,
                    stop_event,
                    ValueError(
                        "Stage worker event identity mismatch: "
                        f"expected={expected_identity!r}, actual={actual_identity!r}."
                    ),
                )
                continue
            callback_index = event.stage_index - 1
            if 0 <= callback_index < len(progress_callbacks):
                callback = progress_callbacks[callback_index]
                if callback is None:
                    continue
                try:
                    callback(
                        event.current,
                        event.total,
                        force=event.force,
                        heartbeat=event.heartbeat,
                    )
                except BaseException as exc:  # pragma: no cover - defensive thread boundary
                    report_first_error(error_queue, stop_event, exc)
            continue
        report_first_error(
            error_queue,
            stop_event,
            ProcessError(
                error_code_to_wire(event.code),
                event.message,
                details=event.details or {},
            ),
        )


def _append_stderr_tail(stderr_tail: deque[str], line: str) -> None:
    encoded_line = line.encode("utf-8")
    if len(encoded_line) > STDERR_TAIL_LIMIT_BYTES:
        line = encoded_line[-STDERR_TAIL_LIMIT_BYTES:].decode("utf-8", errors="replace")
    stderr_tail.append(line)
    while len(stderr_tail) > 1 and sum(len(item.encode("utf-8")) + 1 for item in stderr_tail) > STDERR_TAIL_LIMIT_BYTES:
        stderr_tail.popleft()


__all__ = ["read_worker_stderr"]
