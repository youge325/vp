"""Narrow algorithm ports consumed by stage-worker execution modes."""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class SingleFrameAlgorithm(Protocol):
    def process_frame(self, frame: Any, **kwargs: Any) -> Any: ...


@runtime_checkable
class FramePairAlgorithm(Protocol):
    def process_frame_pair(
        self,
        frame0: Any,
        frame1: Any,
        timestep: float = 0.5,
        **kwargs: Any,
    ) -> Any: ...


@runtime_checkable
class FrameSequenceAlgorithm(Protocol):
    def process_frame_sequence(self, frames: list[Any], **kwargs: Any) -> list[Any]: ...


Algorithm: TypeAlias = SingleFrameAlgorithm | FramePairAlgorithm | FrameSequenceAlgorithm

__all__ = [
    "Algorithm",
    "FramePairAlgorithm",
    "FrameSequenceAlgorithm",
    "SingleFrameAlgorithm",
]
