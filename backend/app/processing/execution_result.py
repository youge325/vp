"""Immutable result returned by every processing execution path."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    output_path: str
    processed_frames: int


__all__ = ["ExecutionResult"]
