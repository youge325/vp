"""允许以 python -m app 方式运行后端。"""

from __future__ import annotations

import json
import traceback


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


try:
    from app.errors import ProcessError
    from app.errors._bootstrap import infer_error_code
except Exception:  # pragma: no cover - defensive bootstrap boundary
    ProcessError = None
    infer_error_code = None


def _bootstrap_error_code(exc: BaseException) -> str:
    """Resolve an error code without depending on a fully-loaded ``app``.

    The primary path delegates to :func:`app.errors._bootstrap.infer_error_code`
    which is the single source of truth for code inference. Only when the
    bootstrap module itself fails to import (catastrophic dependency error
    before the package finishes loading) do we fall back to a minimal inline
    pattern set. Keep this inline list short and aligned with the bootstrap
    module so the two never disagree on the codes they share.
    """
    if infer_error_code is not None:
        return infer_error_code(str(exc).lower())
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
    except Exception as exc:  # pragma: no cover - defensive bootstrap boundary
        code = _bootstrap_error_code(exc)
        _emit(
            {
                "type": "error",
                "code": code,
                "message": str(exc) or exc.__class__.__name__,
                "details": {
                    "exception": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                },
            }
        )
        raise SystemExit(1) from exc

    try:
        main()
    except ProcessError as exc:
        _emit(
            {
                "type": "error",
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        )
        raise SystemExit(1) from exc
    except Exception as exc:  # pragma: no cover - defensive boundary
        if ProcessError is not None:
            pe = ProcessError.from_exception(exc)
            _emit(
                {
                    "type": "error",
                    "code": pe.code,
                    "message": pe.message,
                    "details": pe.details,
                }
            )
        else:
            _emit(
                {
                    "type": "error",
                    "code": _bootstrap_error_code(exc),
                    "message": str(exc) or exc.__class__.__name__,
                    "details": {
                        "exception": exc.__class__.__name__,
                        "traceback": traceback.format_exc(),
                    },
                }
            )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    _run()
