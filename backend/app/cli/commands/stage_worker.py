"""Internal ``stage-worker`` CLI command."""

from __future__ import annotations

import argparse
import sys
import traceback

from app.errors import ProcessError, error_code_to_wire
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.stage_worker import run_stage_worker_stream
from app.processing.streaming.stage_worker_progress import emit_stage_event


def cmd_stage_worker(args: argparse.Namespace) -> None:
    """Run one rawvideo algorithm stage.

    Stdout is reserved for rawvideo bytes. Structured worker events and
    errors are emitted to stderr with ``VP_STAGE_EVENT`` prefix.
    """
    try:
        config = StageWorkerConfig.from_json_file(args.config_json)
        run_stage_worker_stream(
            config,
            sys.stdin.buffer,
            sys.stdout.buffer,
            event_sink=emit_stage_event,
        )
    except BaseException as exc:
        process_error = ProcessError.from_exception(exc)
        emit_stage_event(
            {
                "type": "error",
                "code": error_code_to_wire(process_error.code),
                "message": process_error.message,
                "details": {
                    **process_error.details,
                    "exception": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                },
            }
        )
        raise SystemExit(1) from exc
