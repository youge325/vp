"""Pure-string-match error code inference, safe to import at bootstrap.

This module deliberately depends on nothing from ``app.*`` so that
``__main__`` can import it before resolving the rest of the package.
Both ``errors.from_exception`` and ``__main__`` share these rules.
"""

from __future__ import annotations


def infer_error_code(message: str) -> str:
    """Map a lowercased exception message to a canonical task error code.

    The rules are pattern-match only; type-based branches (e.g. for
    ``FileNotFoundError``) live in :mod:`app.errors`.
    """
    if "ffmpeg" in message or "ffprobe" in message:
        return "missing_ffmpeg"
    if "flownet_v" in message or "model" in message:
        return "missing_model"
    if (
        "no module named 'torch'" in message
        or "no module named torch" in message
        or "pytorch" in message
        or "no module named 'paddle'" in message
        or "no module named paddle" in message
        or "tensor backend" in message
    ):
        return "missing_tensor_backend"
    if "no module named" in message:
        return "missing_python_dependency"
    if "cancelled" in message or "canceled" in message:
        return "cancelled"
    return "process_failed"
