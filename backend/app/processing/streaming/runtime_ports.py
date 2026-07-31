"""Consumer-owned ports for stateful streaming runtime side effects."""

from __future__ import annotations

from typing import Protocol

from app.planning.manifest import ResumeState, SegmentManifest


class ManifestFactoryPort(Protocol):
    """Create a fully composed manifest lifecycle for one output path."""

    def __call__(self, output_path: str) -> SegmentManifest: ...


class ResumeStatusSink(Protocol):
    """Publish one resume status projection without coupling the pipeline to NDJSON."""

    def __call__(self, resume_state: ResumeState, total_output_frames: int) -> None: ...


class WorkerLogSink(Protocol):
    """Consume an ordinary stage-worker stderr line."""

    def __call__(self, line: str) -> None: ...


__all__ = ["ManifestFactoryPort", "ResumeStatusSink", "WorkerLogSink"]
