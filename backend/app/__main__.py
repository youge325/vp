"""允许以 python -m app 方式运行后端。"""

from __future__ import annotations

import json
import traceback


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _infer_bootstrap_error_code(exc: BaseException) -> str:
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
    _emit(
        {
            "type": "error",
            "code": _infer_bootstrap_error_code(exc),
            "message": str(exc) or exc.__class__.__name__,
            "details": {
                "exception": exc.__class__.__name__,
                "traceback": traceback.format_exc(),
            },
        }
    )
    raise SystemExit(1) from exc

try:
    from app.errors import ProcessError

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
