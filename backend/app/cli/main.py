"""CLI entry-point dispatcher.

Sets up logging, parses arguments, dispatches to the chosen
``cmd_*`` handler, and normalizes terminal failures (KeyboardInterrupt
and unexpected exceptions) into ``ProcessError`` for ``__main__.py`` to
render as NDJSON.

Phase C.1.5 — explicit startup hooks:
- ``register_default_algorithms()`` is called explicitly here so the CLI
  startup story is visible at one place, rather than relying on
  ``import app.processing`` to trigger it as a side effect.
- ``register_native_dll_paths()`` is also called early on Windows so the
  loader finds CUDA / TensorRT DLLs before any subsequent ``import
  onnxruntime`` is attempted. The call is still guarded inside
  ``OnnxBackend.__init__`` as a defensive backstop for callers that
  bypass the CLI (e.g. unit tests).
"""

from __future__ import annotations

from app.cli.parser import build_parser
from app.errors import ProcessError, TaskErrorCode, emit_error
from app.processing import register_default_algorithms
from app.utils.dll_paths import register_native_dll_paths
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


def _startup_hooks() -> None:
    """Run the CLI's one-shot setup tasks in a single readable place."""
    setup_logging()
    # 显式注册算法(实际是 idempotent;import app.processing 也会触发)
    register_default_algorithms()
    # Windows 上提前让 OS loader 知道 CUDA/TensorRT DLL 目录,以便后续
    # ``import onnxruntime`` 时 ORT 的静态依赖能解析。非 Windows 上为 no-op。
    register_native_dll_paths()


def main() -> None:
    _startup_hooks()
    parser = build_parser()
    try:
        args = parser.parse_args()
        args.func(args)
    except KeyboardInterrupt:
        emit_error(TaskErrorCode.CANCELLED, "Operation cancelled by the user.", exit_code=130)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        logger.exception("Unhandled backend CLI failure")
        pe = ProcessError.from_exception(exc)
        emit_error(
            pe.code,
            pe.message,
            details={**pe.details, "exception": exc.__class__.__name__},
        )
