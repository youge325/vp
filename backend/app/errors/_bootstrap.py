"""Pure-string-match error code inference, safe to import at bootstrap.

This module deliberately depends on nothing from ``app.*`` (other than the
sibling ``_codes`` module, which itself has no further dependencies) so that
``__main__`` can import it before resolving the rest of the package.
Both ``errors.from_exception`` and ``__main__`` share these rules.
"""

from __future__ import annotations

from app.errors._codes import TaskErrorCode


def infer_error_code(message: str) -> str:
    """Map a lowercased exception message to a canonical task error code.

    The rules are pattern-match only; type-based branches (e.g. for
    ``FileNotFoundError``) live in :mod:`app.errors`.
    """
    if "ffmpeg" in message or "ffprobe" in message:
        return TaskErrorCode.MISSING_FFMPEG.value
    if "flownet_v" in message or "model" in message:
        return TaskErrorCode.MISSING_MODEL.value
    if (
        "no module named 'torch'" in message
        or "no module named torch" in message
        or "pytorch" in message
        or "no module named 'paddle'" in message
        or "no module named paddle" in message
        or "tensor backend" in message
    ):
        return TaskErrorCode.MISSING_TENSOR_BACKEND.value
    if "no module named" in message:
        return TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value
    if "cancelled" in message or "canceled" in message:
        return TaskErrorCode.CANCELLED.value
    return TaskErrorCode.PROCESS_FAILED.value
