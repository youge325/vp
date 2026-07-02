"""Structured process error for the VP Workbench CLI.

All unhandled exceptions that cross the Python→Rust boundary should be
normalized into a ``ProcessError`` so the Rust host can emit a typed
``TaskErrorPayload`` instead of a raw stderr dump.
"""

from __future__ import annotations

import traceback as _traceback
import warnings as _warnings
from typing import Any

from app.errors._bootstrap import infer_error_code
from app.errors._codes import TaskErrorCode, error_code_to_wire


class ProcessError(Exception):
    """Exception carrying a structured error code and optional details dict.

    The ``code`` field should be a ``TaskErrorCode`` enum value when raised
    from application code; the ``__main__`` fallback uses the string
    ``"process_failed"`` for truly unexpected exceptions.

    ``ResumeConflictError`` subclasses this and pre-fills
    ``code=TaskErrorCode.RESUME_CONFLICT`` + details, so the ``__main__``
    error envelope handles it uniformly with every other ``ProcessError``.
    """

    def __init__(
        self,
        code: TaskErrorCode | str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @classmethod
    def from_exception(cls, exc: BaseException) -> "ProcessError":
        """Wrap any exception in a ``ProcessError`` with an inferred code.

        If *exc* is already a ``ProcessError`` it is returned unchanged.
        Delegates the code-inference rules to
        :func:`app.errors._bootstrap.infer_error_code` — the single source
        of truth shared with ``__main__``'s import-time fallback. The
        exception object (not just its message) is forwarded so the
        resolver can apply the Phase 4.1 ``isinstance`` dispatch when no
        keyword in the message gives a more specific answer.
        """
        if isinstance(exc, ProcessError):
            return exc
        code = infer_error_code(exc)
        return cls(
            code,
            str(exc),
            details={"traceback": _traceback.format_exc()},
        )


class ResumeConflictError(ProcessError):
    """Raised when a final output already exists and the user must choose how to proceed.

    Specialises ``ProcessError`` with a fixed ``RESUME_CONFLICT`` code so
    callers can catch it specifically (e.g. to enrich ``details`` with
    ``input_path``) while still benefiting from ``ProcessError``'s direct
    flow through ``__main__``'s error envelope. The ``details`` keys are
    camelCase to match the NDJSON wire format consumed by the Tauri host.
    """

    _DEFAULT_MESSAGE = "An existing output was detected; please choose how to proceed."

    def __init__(
        self,
        *,
        output_path: str,
        completed_chunks: int,
        completed_output_frames: int,
        sidecar_signature_match: bool,
        message: str | None = None,
    ) -> None:
        self.output_path = output_path
        self.completed_chunks = completed_chunks
        self.completed_output_frames = completed_output_frames
        self.sidecar_signature_match = sidecar_signature_match
        super().__init__(
            TaskErrorCode.RESUME_CONFLICT,
            message or self._DEFAULT_MESSAGE,
            details=self.to_details(),
        )

    def to_details(self) -> dict[str, Any]:
        return {
            "outputPath": self.output_path,
            "completedChunks": self.completed_chunks,
            "completedOutputFrames": self.completed_output_frames,
            "sidecarSignatureMatch": self.sidecar_signature_match,
        }


def raise_error(
    code: TaskErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    exit_code: int | None = None,
) -> None:
    """Raise a ``ProcessError`` with the given code, optionally setting ``exit_code``.

    Convenience wrapper used by CLI command handlers to fail-fast. The
    function never returns; the ``None`` return type is for type-checker
    flow analysis at the call site.
    """
    exc = ProcessError(code, message, details=details or {})
    if exit_code is not None:
        exc.exit_code = exit_code  # type: ignore[attr-defined]
    raise exc


def emit_error(
    code: TaskErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    exit_code: int | None = None,
) -> None:
    """Deprecated alias for :func:`raise_error`.

    Kept for one release so external callers can migrate.
    """
    _warnings.warn(
        "emit_error has been renamed to raise_error; the old name will be removed in the next release.",
        DeprecationWarning,
        stacklevel=2,
    )
    raise_error(code, message, details=details, exit_code=exit_code)


__all__ = [
    "ProcessError",
    "ResumeConflictError",
    "TaskErrorCode",
    "emit_error",
    "error_code_to_wire",
    "raise_error",
]
