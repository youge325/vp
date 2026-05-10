"""Structured process error for the VP Workbench CLI.

All unhandled exceptions that cross the Python→Rust boundary should be
normalized into a ``ProcessError`` so the Rust host can emit a typed
``TaskErrorPayload`` instead of a raw stderr dump.
"""

from __future__ import annotations

import traceback as _traceback
from typing import Any


def _infer_code_from_exception(exc: BaseException) -> str:
    """Map an exception to a canonical error code string.

    Centralises the inference rules that were previously duplicated in
    ``cli._infer_error_code`` and ``__main__._infer_bootstrap_error_code``.
    """
    message = str(exc).lower()

    if isinstance(exc, FileNotFoundError):
        if "ffmpeg" in message or "ffprobe" in message:
            return "missing_ffmpeg"
        if "flownet_v" in message or "model" in message:
            return "missing_model"

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
    if "cancelled" in message or "canceled" in message:
        return "cancelled"

    return "process_failed"


class ProcessError(Exception):
    """Exception carrying a structured error code and optional details dict.

    The ``code`` field should be a ``TaskErrorCode`` enum value when raised
    from application code; the ``__main__`` fallback uses the string
    ``"process_failed"`` for truly unexpected exceptions.
    """

    def __init__(
        self,
        code: str,
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
        """
        if isinstance(exc, ProcessError):
            return exc
        code = _infer_code_from_exception(exc)
        return cls(
            code,
            str(exc),
            details={"traceback": _traceback.format_exc()},
        )


class ResumeConflictError(Exception):
    """Raised when a final output already exists and the user must choose how to proceed."""

    def __init__(
        self,
        *,
        output_path: str,
        completed_chunks: int,
        completed_output_frames: int,
        sidecar_signature_match: bool,
    ) -> None:
        super().__init__(f"Final output already exists at {output_path}; user decision required.")
        self.output_path = output_path
        self.completed_chunks = completed_chunks
        self.completed_output_frames = completed_output_frames
        self.sidecar_signature_match = sidecar_signature_match

    def to_details(self) -> dict[str, Any]:
        return {
            "outputPath": self.output_path,
            "completedChunks": self.completed_chunks,
            "completedOutputFrames": self.completed_output_frames,
            "sidecarSignatureMatch": self.sidecar_signature_match,
        }
