"""Centralised NDJSON protocol emitter for the VP Workbench CLI.

All structured events written to stdout must pass through :class:`NdjsonEmitter`
so the format, field names and envelope shape stay consistent across the
pipeline.  Ordinary log lines and terminal progress bars continue to go to
stderr and are *not* handled here.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from app.protocol.payloads import (
    ResumeStatusPayload,
    TaskCompletedPayload,
    TaskErrorPayload,
    TaskProgressPayload,
)


# SSOT for NDJSON wire names. Cross-language drift is gated by
# ``scripts/check_error_code_drift.py`` (Phase 9):
#   - Stream variants (read by ``frontend/src-tauri/src/tasks/envelope.rs``
#     ``NdjsonEnvelope``) must round-trip both ways.
#   - Oneshot-only variants (read by ``oneshot.rs::parse_last_json_line``
#     as a generic ``Value``) are listed in the script's
#     ``NDJSON_ONESHOT_WHITELIST`` constant.
# Adding a new member here requires either a matching ``NdjsonEnvelope``
# variant + ``readers.rs`` route, or an explicit whitelist update.
class NdjsonEventType(str, Enum):
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"
    RESUME_STATUS = "resume_status"
    RESUME_INSPECTION = "resume_inspection"
    INFO = "info"
    CHECK = "check"


class _NdjsonEmitter:
    """Emitter for NDJSON events on stdout.

    Thread-safe because Python's GIL serialises ``print()`` calls and each
    call is a single atomic write after JSON serialisation.
    """

    def _emit(self, event_type: NdjsonEventType, data: dict[str, Any]) -> None:
        envelope = {"type": event_type.value, **data}
        print(json.dumps(envelope, ensure_ascii=False), flush=True)

    # --- Convenience helpers ---

    def progress(
        self,
        current: int,
        total: int,
        percent: float,
        stage: str,
        stage_index: int,
        stage_total: int,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        payload = TaskProgressPayload(
            current=current,
            total=total,
            percent=percent,
            stage=stage,
            stage_index=stage_index,
            stage_total=stage_total,
            # Phase D.2.3 — pipeline observability rides along on the
            # progress frame. Empty snapshots keep the old "field absent"
            # wire shape.
            metrics=metrics if metrics else None,
        )
        self._emit(NdjsonEventType.PROGRESS, payload.to_wire())

    def completed(
        self,
        output_path: str,
        processed_frames: int,
        time_seconds: float,
    ) -> None:
        payload = TaskCompletedPayload(
            output_path=output_path,
            processed_frames=processed_frames,
            time_seconds=time_seconds,
        )
        self._emit(NdjsonEventType.COMPLETED, payload.to_wire())

    def error(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = TaskErrorPayload(code=code, message=message, details=details or {})
        self._emit(NdjsonEventType.ERROR, payload.to_wire())

    def resume_status(
        self,
        resumed: bool,
        completed_chunks: int,
        completed_output_frames: int,
        start_source_frame: int,
        total_output_frames: int,
    ) -> None:
        payload = ResumeStatusPayload(
            resumed=resumed,
            completed_chunks=completed_chunks,
            completed_output_frames=completed_output_frames,
            start_source_frame=start_source_frame,
            total_output_frames=total_output_frames,
        )
        self._emit(NdjsonEventType.RESUME_STATUS, payload.to_wire())

    def resume_inspection(self, **kwargs: Any) -> None:
        self._emit(NdjsonEventType.RESUME_INSPECTION, kwargs)

    def info(self, **kwargs: Any) -> None:
        self._emit(NdjsonEventType.INFO, kwargs)

    def check(self, **kwargs: Any) -> None:
        self._emit(NdjsonEventType.CHECK, kwargs)


# Module-level convenience alias
ndjson = _NdjsonEmitter()
