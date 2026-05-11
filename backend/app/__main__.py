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
    """Resolve an error code without depending on a fully-loaded ``app``."""
    if infer_error_code is not None:
        return infer_error_code(str(exc).lower())
    # Fallback if even ``app.errors._bootstrap`` failed to import.
    message = str(exc).lower()
    if "no module named" in message:
        if "torch" in message or "paddle" in message:
            return "missing_tensor_backend"
        return "missing_python_dependency"
    if "ffmpeg" in message or "ffprobe" in message:
        return "missing_ffmpeg"
    return "process_failed"


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
