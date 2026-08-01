"""Internal ``stage-worker`` CLI command."""

from __future__ import annotations

import argparse
import sys
import traceback

from app.config import settings
from app.errors.codes import error_code_to_wire
from app.errors.process import ProcessError
from app.generated.stage_worker_contracts import BackendTaskErrorCode, StageWorkerErrorEvent
from app.processing.streaming.stage_worker import run_stage_worker_stream
from app.processing.streaming.stage_worker_config import load_stage_worker_config
from app.processing.streaming.stage_worker_progress import emit_stage_event
from app.protocol.encoding import bound_error_fields


def cmd_stage_worker(args: argparse.Namespace) -> None:
    """Run one rawvideo algorithm stage.

    Stdout is reserved for rawvideo bytes. Structured worker events and
    errors are emitted to stderr with the generated stage-worker event prefix.
    """
    try:
        config = load_stage_worker_config(args.config_json)
        run_stage_worker_stream(
            config,
            sys.stdin.buffer,
            sys.stdout.buffer,
            event_sink=emit_stage_event,
            model_root=settings.RIFE_MODEL_DIR,
        )
    except BaseException as exc:
        process_error = ProcessError.from_exception(exc)
        message, details = bound_error_fields(
            process_error.message,
            {
                **process_error.details,
                "exception": exc.__class__.__name__,
                "traceback": traceback.format_exc(),
            },
        )
        try:
            emit_stage_event(
                StageWorkerErrorEvent(
                    type="error",
                    code=BackendTaskErrorCode(error_code_to_wire(process_error.code)),
                    message=message,
                    details=details,
                )
            )
        except BaseException as emit_error:  # pragma: no cover - broken stderr boundary
            exc.add_note(f"Could not emit the stage-worker error event: {emit_error!r}")
        raise SystemExit(1) from exc
