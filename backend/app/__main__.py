"""允许以 python -m app 方式运行后端。"""

from __future__ import annotations

import json
import traceback


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


try:
    from app.errors import ProcessError
except Exception:  # pragma: no cover - defensive bootstrap boundary
    ProcessError = None


def _infer_bootstrap_error_code(exc: BaseException) -> str:
    """Bootstrap-time fallback for error-code inference.

    Once ``app.errors`` is importable the canonical
    :func:`app.errors._infer_code_from_exception` should be used instead.
    """
    message = str(exc).lower()
    if "no module named" in message:
        if "torch" in message or "paddle" in message:
            return "missing_tensor_backend"
        return "missing_python_dependency"
    if "ffmpeg" in message or "ffprobe" in message:
        return "missing_ffmpeg"
    if "flownet_v" in message or "model" in message:
        return "missing_model"
    return "process_failed"


try:
    from app.cli import main
except Exception as exc:  # pragma: no cover - defensive bootstrap boundary
    code = _infer_bootstrap_error_code(exc)
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
                "code": "process_failed",
                "message": str(exc) or exc.__class__.__name__,
                "details": {
                    "exception": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                },
            }
        )
    raise SystemExit(1) from exc
