"""Narrow algorithm ports consumed by stage-worker execution modes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class SingleFrameAlgorithm(Protocol):
    def process_frame(self, frame: Any) -> Any: ...


@runtime_checkable
class NumpyFrameAlgorithm(Protocol):
    def process_numpy(self, frame: Any) -> Any: ...


@runtime_checkable
class FramePairAlgorithm(Protocol):
    def process_frame_pair(
        self,
        frame0: Any,
        frame1: Any,
        *,
        timestep: float,
    ) -> Any: ...


@runtime_checkable
class FrameSequenceAlgorithm(Protocol):
    def process_frame_sequence(
        self,
        frames: list[Any],
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[Any]: ...


Algorithm: TypeAlias = NumpyFrameAlgorithm | SingleFrameAlgorithm | FramePairAlgorithm | FrameSequenceAlgorithm

__all__ = [
    "Algorithm",
    "FramePairAlgorithm",
    "FrameSequenceAlgorithm",
    "NumpyFrameAlgorithm",
    "SingleFrameAlgorithm",
]
