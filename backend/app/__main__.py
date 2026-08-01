"""允许以 python -m app 方式运行后端。"""

from __future__ import annotations

import sys
import traceback
from typing import Any

from app.generated.bootstrap_constants import BACKEND_TASK_ERROR_CODES
from app.protocol.encoding import bound_error_fields, encode_bounded_json_line

try:
    from app.errors.bootstrap import infer_bootstrap_error_code
except Exception:  # pragma: no cover - catastrophic bootstrap boundary
    infer_bootstrap_error_code = None


def _emit(payload: dict) -> None:
    sys.stdout.write(encode_bounded_json_line(payload))
    sys.stdout.flush()


def _emit_error_payload(code: object, message: str, details: dict) -> None:
    """Emit an import-safe error envelope before protocol modules are available."""
    bounded_message, bounded_details = bound_error_fields(message, details)
    _emit(
        {
            "type": "error",
            "code": _wire_error_code(code),
            "message": bounded_message,
            "details": bounded_details,
        }
    )


def _emit_typed_error(emitter: Any, error: Any) -> None:
    from app.generated.contracts import BackendTaskErrorPayload
    from app.generated.protocol_constants import BackendEnvelopeType

    bounded_message, bounded_details = bound_error_fields(error.message, error.details or {})
    emitter.emit(
        BackendEnvelopeType.ERROR,
        BackendTaskErrorPayload(
            code=_wire_error_code(error.code),
            message=bounded_message,
            details=bounded_details,
        ),
    )


def _emit_unhandled_exception(exc: BaseException) -> None:
    _emit_error_payload(
        _bootstrap_error_code(exc),
        str(exc) or exc.__class__.__name__,
        {
            "exception": exc.__class__.__name__,
            "traceback": traceback.format_exc(),
        },
    )


try:
    from app.errors.codes import error_code_to_wire
    from app.errors.process import ProcessError
except Exception:  # pragma: no cover - defensive bootstrap boundary
    ProcessError = None
    error_code_to_wire = None


def _wire_error_code(code: object) -> str:
    if error_code_to_wire is not None:
        return error_code_to_wire(code)
    if isinstance(code, str) and code in BACKEND_TASK_ERROR_CODES:
        return code
    return "process_failed"


def _bootstrap_error_code(exc: BaseException) -> str:
    """Resolve an error code without depending on a fully-loaded ``app``.

    The import-safe bootstrap module is the only owner of inference rules.
    If even that standard-library-only module cannot load, fail closed to the
    generated protocol's generic error code rather than maintaining a mirror.
    """
    return infer_bootstrap_error_code(exc) if infer_bootstrap_error_code is not None else "process_failed"


def _run() -> None:
    """Execute the CLI. Wrapped so `import app.__main__` does not invoke it."""
    try:
        from app.cli.main import main
        from app.protocol.emitter import ndjson
    except Exception as exc:  # pragma: no cover - defensive bootstrap boundary
        _emit_unhandled_exception(exc)
        raise SystemExit(1) from exc

    try:
        main()
    except ProcessError as exc:
        _emit_typed_error(ndjson, exc)
        raise SystemExit(1) from exc
    except Exception as exc:  # pragma: no cover - defensive boundary
        if ProcessError is not None:
            _emit_typed_error(ndjson, ProcessError.from_exception(exc))
        else:
            _emit_unhandled_exception(exc)
        raise SystemExit(1) from exc


def _close_late_cleanup() -> None:
    module = sys.modules.get("app.utils.late_cleanup")
    if module is not None:
        module.late_cleanup_coordinator.close()


if __name__ == "__main__":
    try:
        _run()
    finally:
        _close_late_cleanup()
