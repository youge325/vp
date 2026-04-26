"""允许以 python -m app 方式运行后端。"""

from __future__ import annotations

import json
import sys
import traceback


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
    traceback.print_exc(file=sys.stderr)
    print(
        json.dumps(
            {
                "type": "error",
                "code": _infer_bootstrap_error_code(exc),
                "message": str(exc) or exc.__class__.__name__,
                "details": {"exception": exc.__class__.__name__},
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    raise SystemExit(1) from exc

main()
