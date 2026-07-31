"""CLI entry-point dispatcher.

Sets up logging, parses arguments, dispatches to the chosen
``cmd_*`` handler, and normalizes terminal failures (KeyboardInterrupt
and unexpected exceptions) into ``ProcessError`` for ``__main__.py`` to
render as NDJSON.

Stage workers intentionally avoid global algorithm startup: each worker
registers exactly one algorithm stage after reading its config, keeping
PyTorch / Paddle / ONNX runtime DLL loading isolated by process.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import importlib

from app.cli.parser import build_parser
from app.errors import ProcessError, TaskErrorCode, error_code_to_wire, raise_error
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

_HANDLERS: dict[str, tuple[str, str]] = {
    "benchmark": ("app.cli.commands.benchmark", "cmd_benchmark"),
    "check": ("app.cli.commands.check", "cmd_check"),
    "info": ("app.cli.commands.info", "cmd_info"),
    "inspect_output": ("app.cli.commands.inspect_output", "cmd_inspect_output"),
    "process": ("app.cli.commands.process", "cmd_process"),
    "stage_worker": ("app.cli.commands.stage_worker", "cmd_stage_worker"),
}


def _load_handler(name: str) -> Callable[[argparse.Namespace], None]:
    try:
        module_name, symbol_name = _HANDLERS[name]
    except KeyError as exc:  # pragma: no cover - parser owns valid identifiers
        raise RuntimeError(f"Unknown CLI handler: {name!r}") from exc
    handler = getattr(importlib.import_module(module_name), symbol_name)
    if not callable(handler):  # pragma: no cover - static registry invariant
        raise TypeError(f"CLI handler {module_name}.{symbol_name} is not callable.")
    return handler


def main() -> None:
    parser = build_parser()
    try:
        args = parser.parse_args()
        setup_logging()
        _load_handler(args.handler)(args)
    except KeyboardInterrupt:
        raise_error(TaskErrorCode.CANCELLED, "Operation cancelled by the user.")
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        logger.exception("Unhandled backend CLI failure")
        pe = ProcessError.from_exception(exc)
        raise_error(
            error_code_to_wire(pe.code),
            pe.message,
            details={**pe.details, "exception": exc.__class__.__name__},
        )
