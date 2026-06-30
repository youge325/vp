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

from app.cli.parser import build_parser
from app.errors import ProcessError, TaskErrorCode, raise_error
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


def _startup_hooks() -> None:
    """Run the CLI's one-shot setup tasks in a single readable place."""
    setup_logging()


def main() -> None:
    parser = build_parser()
    try:
        args = parser.parse_args()
        _startup_hooks()
        args.func(args)
    except KeyboardInterrupt:
        raise_error(TaskErrorCode.CANCELLED, "Operation cancelled by the user.", exit_code=130)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        logger.exception("Unhandled backend CLI failure")
        pe = ProcessError.from_exception(exc)
        raise_error(
            pe.code,
            pe.message,
            details={**pe.details, "exception": exc.__class__.__name__},
        )
