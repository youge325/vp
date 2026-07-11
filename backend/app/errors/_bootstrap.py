"""Pure error-code inference, safe to import at bootstrap.

This module deliberately depends on nothing from ``app.*`` (other than the
sibling ``_codes`` module, which itself has no further dependencies) so that
``__main__`` can import it before resolving the rest of the package.
Both ``errors.from_exception`` and ``__main__`` share these rules.

``infer_error_code`` accepts the exception itself and resolves it in two
passes:

1. **Message-pattern pass.** Existing keyword rules (ffmpeg / flownet /
   torch / paddle / no module named / cancel) win first so that long-lived
   downstream behavior — e.g. a ``FileNotFoundError("ffmpeg")`` mapping to
   ``MISSING_FFMPEG`` rather than the generic ``IO_ERROR`` — is preserved.
2. **stdlib type dispatch.** Only when the message offers no specific
   signal do we fall back to broad ``isinstance`` buckets:
   ``ImportError`` / ``ModuleNotFoundError`` → ``MISSING_PYTHON_DEPENDENCY``,
   ``FileNotFoundError`` / ``PermissionError`` → ``IO_ERROR``,
   ``ValueError`` / ``TypeError`` → ``INVALID_INPUT``.

Phase 11 — ``MISSING_MODEL`` 的关键字从单字符串 ``"model"`` 缩窄到
``"flownet_v" / "model file" / "model weight" / "missing model"``。原来
任意 message 含 "model" 都会被归类 MISSING_MODEL,导致 Pydantic
ValidationError 文本里的字段名(如 ``"model_x has invalid type"``)被误
归类。**保留**message-first 优先级——文件顶部的 ffmpeg 规则就靠它让
``FileNotFoundError("ffmpeg")`` 落到 MISSING_FFMPEG 而非 IO_ERROR,反转
会回退此行为。
"""

from __future__ import annotations

from app.errors._codes import TaskErrorCode


def _match_by_message(message: str) -> str:
    """Return a TaskErrorCode for messages with a recognised keyword, or PROCESS_FAILED."""
    if "ffmpeg" in message or "ffprobe" in message:
        return TaskErrorCode.MISSING_FFMPEG.value
    if "flownet_v" in message or "model file" in message or "model weight" in message or "missing model" in message:
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


def _dispatch_by_type(exc: BaseException) -> str | None:
    """Map common stdlib exception types to coarse TaskErrorCode buckets.

    Returns ``None`` when no bucket applies, signalling the caller to fall
    through to ``PROCESS_FAILED``.
    """
    if isinstance(exc, (ModuleNotFoundError, ImportError)):
        return TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return TaskErrorCode.IO_ERROR.value
    if isinstance(exc, (ValueError, TypeError)):
        return TaskErrorCode.INVALID_INPUT.value
    return None


def infer_error_code(exc: BaseException) -> str:
    """Resolve the canonical task error code for *exc*.

    Message matches like ``"ffmpeg"`` keep their specific code before the
    resolver falls back to coarse ``isinstance`` buckets.
    """
    message_hit = _match_by_message(str(exc).lower())
    if message_hit != TaskErrorCode.PROCESS_FAILED.value:
        return message_hit
    bucket = _dispatch_by_type(exc)
    if bucket is not None:
        return bucket
    return TaskErrorCode.PROCESS_FAILED.value
