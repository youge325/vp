"""Lightweight streaming runtime ports for focused unit tests."""

from __future__ import annotations

from app.planning.manifest import ResumeState, SegmentManifest
from app.planning.manifest_store import ManifestRepository
from app.planning.segment_workspace import SegmentWorkspace


def create_test_manifest(output_path: str) -> SegmentManifest:
    workspace = SegmentWorkspace.for_output(output_path)
    return SegmentManifest(workspace=workspace, repository=ManifestRepository(workspace))


def ignore_resume_status(_resume_state: ResumeState, _total_output_frames: int) -> None:
    return None


def ignore_worker_log(_line: str) -> None:
    return None
