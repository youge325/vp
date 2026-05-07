"""Structured process error for the VP Workbench CLI.

All unhandled exceptions that cross the Python→Rust boundary should be
normalized into a ``ProcessError`` so the Rust host can emit a typed
``TaskErrorPayload`` instead of a raw stderr dump.
"""

from __future__ import annotations

from typing import Any


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
