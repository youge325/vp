"""允许以 python -m app 方式运行后端。"""

from __future__ import annotations

import json
import traceback


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _emit_error_payload(code: object, message: str, details: dict) -> None:
    """Emit an import-safe error envelope before protocol modules are available."""
    _emit(
        {
            "type": "error",
            "code": _wire_error_code(code),
            "message": message,
            "details": details,
        }
    )


try:
    from app.errors import ProcessError, error_code_to_wire
    from app.errors._bootstrap import infer_error_code
except Exception:  # pragma: no cover - defensive bootstrap boundary
    ProcessError = None
    error_code_to_wire = None
    infer_error_code = None


def _wire_error_code(code: object) -> str:
    if error_code_to_wire is not None:
        return error_code_to_wire(code)
    if isinstance(code, str) and code in {
        "missing_ffmpeg",
        "missing_model",
        "missing_tensor_backend",
        "missing_python_dependency",
        "cancelled",
        "process_failed",
        "spawn_failed",
        "runtime_panic",
        "invalid_input",
        "invalid_config",
        "resume_conflict",
        "io_error",
        "schema_mismatch",
        "persistence_failed",
        "backend_no_json",
        "backend_envelope",
        "controller_unavailable",
        "backend_probe_failed",
    }:
        return code
    return "process_failed"


def _bootstrap_error_code(exc: BaseException) -> str:
    """Resolve an error code without depending on a fully-loaded ``app``.

    The primary path delegates to :func:`app.errors._bootstrap.infer_error_code`
    which is the single source of truth for code inference. The full
    exception object is forwarded so the bootstrap-mode resolver can run
    its Phase 4.1 ``isinstance`` dispatch even before the rest of ``app``
    is importable. Only when the bootstrap module itself fails to import
    (catastrophic dependency error before the package finishes loading)
    do we fall back to a minimal inline pattern set. Keep this inline list
    short and aligned with the bootstrap module so the two never disagree
    on the codes they share.
    """
    if infer_error_code is not None:
        return infer_error_code(exc)
    # Bootstrap-only fallback: ``app.errors._bootstrap`` failed to import,
    # so we cannot share rules. Mirror the most common cases verbatim.
    message = str(exc).lower()
    if "no module named" in message:
        if "torch" in message or "paddle" in message:
            return "missing_tensor_backend"
        return "missing_python_dependency"
    if "ffmpeg" in message or "ffprobe" in message:
        return "missing_ffmpeg"
    return "process_failed"


def _run() -> None:
    """Execute the CLI. Wrapped so `import app.__main__` does not invoke it."""
    try:
        from app.cli import main
        from app.protocol import ndjson
    except Exception as exc:  # pragma: no cover - defensive bootstrap boundary
        _emit_error_payload(
            _bootstrap_error_code(exc),
            str(exc) or exc.__class__.__name__,
            {
                "exception": exc.__class__.__name__,
                "traceback": traceback.format_exc(),
            },
        )
        raise SystemExit(1) from exc

    try:
        main()
    except ProcessError as exc:
        ndjson.error(
            code=_wire_error_code(exc.code),
            message=exc.message,
            details=exc.details,
        )
        raise SystemExit(1) from exc
    except Exception as exc:  # pragma: no cover - defensive boundary
        if ProcessError is not None:
            pe = ProcessError.from_exception(exc)
            ndjson.error(
                code=_wire_error_code(pe.code),
                message=pe.message,
                details=pe.details,
            )
        else:
            _emit_error_payload(
                _bootstrap_error_code(exc),
                str(exc) or exc.__class__.__name__,
                {
                    "exception": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                },
            )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    _run()
