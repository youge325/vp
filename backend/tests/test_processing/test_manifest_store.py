"""Focused tests for resume manifest JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.planning.manifest_store as manifest_store
from app.errors import ProcessError, TaskErrorCode
from tests.support.streaming_runtime import create_test_manifest
from app.planning.segment_workspace import SegmentWorkspace


@pytest.mark.parametrize(
    "contents",
    [
        "{not json",
        json.dumps({"version": manifest_store._MANIFEST_VERSION - 1, "signature": "old"}),
        json.dumps({"version": manifest_store._MANIFEST_VERSION, "signature": "missing-fields"}),
        json.dumps(
            {
                "version": manifest_store._MANIFEST_VERSION,
                "signature": "extra-field",
                "created_at": "2026-07-28T00:00:00Z",
                "input_path": "input.mp4",
                "output_path": "output.mp4",
                "config_snapshot": {},
                "unexpected": True,
            }
        ),
        json.dumps(["not", "an", "object"]),
    ],
)
def test_load_manifest_rejects_invalid_payloads(tmp_path: Path, contents: str) -> None:
    workspace = SegmentWorkspace.for_output(tmp_path / "output.mp4")
    workspace.ensure()
    workspace.manifest_path.write_text(contents, encoding="utf-8")

    assert manifest_store.ManifestRepository(workspace).load() is None


def test_write_manifest_uses_atomic_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "output.mp4"
    workspace = SegmentWorkspace.for_output(output_path)
    manifest_path = workspace.manifest_path
    captured: list[tuple[str, str]] = []
    real_replace = manifest_store.os.replace

    def tracking_replace(src: str | Path, dst: str | Path) -> None:
        captured.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(manifest_store.os, "replace", tracking_replace)

    manifest_store.ManifestRepository(workspace).write(
        signature="sig-a",
        config_snapshot={"input_path": "input.mp4", "quality": 18},
    )

    assert captured == [(str(manifest_path.with_suffix(".json.tmp")), str(manifest_path))]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload == {
        "version": manifest_store._MANIFEST_VERSION,
        "signature": "sig-a",
        "created_at": payload["created_at"],
        "input_path": "input.mp4",
        "output_path": str(output_path),
        "config_snapshot": {"input_path": "input.mp4", "quality": 18},
    }
    assert payload["created_at"].endswith("Z")
    assert not manifest_path.with_suffix(".json.tmp").exists()


def test_manifest_read_error_is_not_misclassified_or_quarantined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = create_test_manifest(str(tmp_path / "output.mp4"))
    manifest.workspace.ensure()
    manifest.workspace.manifest_path.write_text("keep", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def deny_manifest_read(path: Path) -> bytes:
        if path == manifest.workspace.manifest_path:
            raise PermissionError("read denied")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny_manifest_read)

    with pytest.raises(ProcessError, match="Unable to read segment manifest") as exc_info:
        manifest.prepare("signature")

    assert exc_info.value.code == TaskErrorCode.PERSISTENCE_FAILED
    assert exc_info.value.details["operation"] == "read"
    assert manifest.workspace.sidecar_dir.is_dir()
    assert not list(tmp_path.glob("output.mp4.vp_segments.incompatible*"))


def test_manifest_fsync_failure_is_reported_and_partial_file_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SegmentWorkspace.for_output(tmp_path / "output.mp4")

    def fail_fsync(_file_descriptor: int) -> None:
        raise OSError("flush denied")

    monkeypatch.setattr(manifest_store.os, "fsync", fail_fsync)

    with pytest.raises(ProcessError, match="Unable to write segment manifest") as exc_info:
        manifest_store.ManifestRepository(workspace).write(
            signature="signature",
            config_snapshot={},
        )

    assert exc_info.value.code == TaskErrorCode.PERSISTENCE_FAILED
    assert exc_info.value.details["operation"] == "write"
    assert not workspace.manifest_path.exists()
    assert not workspace.manifest_path.with_suffix(".json.tmp").exists()


def test_manifest_workspace_creation_failure_is_classified_as_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = SegmentWorkspace.for_output(tmp_path / "output.mp4")

    def deny_workspace_creation(_workspace: SegmentWorkspace) -> None:
        raise PermissionError("directory denied")

    monkeypatch.setattr(SegmentWorkspace, "ensure", deny_workspace_creation)

    with pytest.raises(ProcessError, match="Unable to write segment manifest") as exc_info:
        manifest_store.ManifestRepository(workspace).write(
            signature="signature",
            config_snapshot={},
        )

    assert exc_info.value.code == TaskErrorCode.PERSISTENCE_FAILED
    assert exc_info.value.details == {
        "operation": "write",
        "path": str(workspace.manifest_path),
    }


def test_non_utf8_manifest_is_treated_as_corrupt_data(tmp_path: Path) -> None:
    workspace = SegmentWorkspace.for_output(tmp_path / "output.mp4")
    workspace.ensure()
    workspace.manifest_path.write_bytes(b"\xff\xfe")

    assert manifest_store.ManifestRepository(workspace).load() is None
