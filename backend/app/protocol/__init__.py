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


class NdjsonEmitter:
    """Singleton emitter for NDJSON events on stdout.

    Thread-safe because Python's GIL serialises ``print()`` calls and each
    call is a single atomic write after JSON serialisation.
    """

    _instance: "NdjsonEmitter | None" = None

    def __new__(cls) -> "NdjsonEmitter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

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
        payload: dict[str, Any] = {
            "current": current,
            "total": total,
            "percent": percent,
            "stage": stage,
            "stageIndex": stage_index,
            "stageTotal": stage_total,
        }
        # Phase D.2.3 — pipeline observability rides along on the progress
        # frame. Fields land under ``metrics`` so the existing top-level
        # schema stays untouched and Rust / older clients can ignore the
        # bag entirely.
        if metrics:
            payload["metrics"] = metrics
        self._emit(NdjsonEventType.PROGRESS, payload)

    def completed(
        self,
        output_path: str,
        processed_frames: int,
        time_seconds: float,
    ) -> None:
        self._emit(
            NdjsonEventType.COMPLETED,
            {
                "outputPath": output_path,
                "processedFrames": processed_frames,
                "timeSeconds": time_seconds,
            },
        )

    def error(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            NdjsonEventType.ERROR,
            {
                "code": code,
                "message": message,
                "details": details or {},
            },
        )

    def resume_status(
        self,
        resumed: bool,
        completed_chunks: int,
        completed_output_frames: int,
        start_source_frame: int,
        total_output_frames: int,
    ) -> None:
        self._emit(
            NdjsonEventType.RESUME_STATUS,
            {
                "resumed": resumed,
                "completedChunks": completed_chunks,
                "completedOutputFrames": completed_output_frames,
                "startSourceFrame": start_source_frame,
                "totalOutputFrames": total_output_frames,
            },
        )

    def resume_inspection(self, **kwargs: Any) -> None:
        self._emit(NdjsonEventType.RESUME_INSPECTION, kwargs)

    def info(self, **kwargs: Any) -> None:
        self._emit(NdjsonEventType.INFO, kwargs)

    def check(self, **kwargs: Any) -> None:
        self._emit(NdjsonEventType.CHECK, kwargs)


# Module-level convenience alias
ndjson = NdjsonEmitter()
