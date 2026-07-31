"""CLI adapters for streaming runtime persistence and observation ports."""

from __future__ import annotations

import sys

from app.generated.contracts import ResumeStatusPayload
from app.generated.protocol_constants import BackendEnvelopeType
from app.planning.manifest import ResumeState, SegmentManifest
from app.planning.manifest_store import ManifestRepository
from app.planning.segment_workspace import SegmentWorkspace
from app.protocol import ndjson
from app.protocol.process_markers import TENSORRT_LOG_PREFIX


class FilesystemManifestFactory:
    """Compose workspace, repository, and lifecycle at the CLI boundary."""

    def __call__(self, output_path: str) -> SegmentManifest:
        workspace = SegmentWorkspace.for_output(output_path)
        return SegmentManifest(
            workspace=workspace,
            repository=ManifestRepository(workspace),
        )


class NdjsonResumeStatusSink:
    """Publish resume status through the generated backend envelope."""

    def __call__(self, resume_state: ResumeState, total_output_frames: int) -> None:
        ndjson.emit(
            BackendEnvelopeType.RESUME_STATUS,
            ResumeStatusPayload(
                resumed=resume_state.completed_output_frames > 0,
                completed_chunks=len(resume_state.completed_segments),
                completed_output_frames=resume_state.completed_output_frames,
                start_source_frame=resume_state.start_source_frame,
                total_output_frames=total_output_frames,
            ),
        )


class CliWorkerLogSink:
    """Forward only user-relevant TensorRT worker diagnostics to the CLI host."""

    def __call__(self, line: str) -> None:
        if TENSORRT_LOG_PREFIX in line:
            print(line, file=sys.stderr, flush=True)


__all__ = ["CliWorkerLogSink", "FilesystemManifestFactory", "NdjsonResumeStatusSink"]
