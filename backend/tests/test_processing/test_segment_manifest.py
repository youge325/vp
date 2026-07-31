"""Unit tests for the filesystem-as-state SegmentManifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.errors import ResumeConflictError
from app.generated.contracts import SegmentManifest as SegmentManifestContract
from app.planning.manifest import SegmentManifest
from app.planning.manifest_store import _MANIFEST_VERSION
from app.planning.segment_workspace import SegmentWorkspace
from tests.support.streaming_runtime import create_test_manifest


class _FakeManifestRepository:
    def __init__(self) -> None:
        self.value: SegmentManifestContract | None = None
        self.writes: list[tuple[str, dict[str, object]]] = []

    def load(self) -> SegmentManifestContract | None:
        return self.value

    def write(self, *, signature: str, config_snapshot: dict[str, object]) -> None:
        self.writes.append((signature, config_snapshot))


def _make_chunk(sidecar: Path, *, index: int, start: int, end: int, next_src: int) -> Path:
    name = f"chunk-{index:04d}-out{start:08d}-{end:08d}-src{next_src:08d}.mp4"
    path = sidecar / name
    path.write_bytes(b"chunk")
    return path


def test_prepare_fresh_when_sidecar_missing(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    decision = manifest.prepare("sig-1", {"foo": "bar"}, mode="auto")

    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert decision.state.start_source_frame == 0
    assert decision.state.completed_segments == []
    assert manifest.workspace.manifest_path.is_file()
    payload = json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == _MANIFEST_VERSION
    assert payload["signature"] == "sig-1"
    assert payload["config_snapshot"] == {"foo": "bar"}
    assert "segments" not in payload  # progress is filesystem-derived


def test_manifest_uses_injected_repository_port(tmp_path: Path) -> None:
    workspace = SegmentWorkspace.for_output(tmp_path / "out.mp4")
    repository = _FakeManifestRepository()
    manifest = SegmentManifest(workspace=workspace, repository=repository)

    decision = manifest.prepare("sig-port", {"input_path": "input.mp4"})

    assert decision.kind == "fresh"
    assert repository.writes == [("sig-port", {"input_path": "input.mp4"})]
    assert not workspace.manifest_path.exists()


def test_prepare_resume_with_contiguous_chunks(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-2", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=999, next_src=500)
    _make_chunk(manifest.workspace.sidecar_dir, index=2, start=1000, end=1499, next_src=750)

    decision = manifest.prepare("sig-2", {}, mode="auto")
    assert decision.kind == "resume"
    assert decision.state.completed_output_frames == 1500
    assert decision.state.start_source_frame == 750
    assert [chunk.index for chunk in decision.state.completed_segments] == [1, 2]


def test_prepare_resets_on_signature_mismatch(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-old", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=999, next_src=500)

    decision = manifest.prepare("sig-new", {}, mode="auto")
    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert manifest.workspace.manifest_path.is_file()
    chunks = list(p.name for p in manifest.workspace.sidecar_dir.iterdir() if p.name.startswith("chunk-"))
    assert chunks == []


def test_prepare_recovers_from_corrupt_manifest(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.workspace.sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest.workspace.manifest_path.write_text("{not json", encoding="utf-8")

    decision = manifest.prepare("sig-3", {}, mode="auto")
    assert decision.kind == "fresh"
    assert manifest.workspace.manifest_path.is_file()
    payload = json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))
    assert payload["signature"] == "sig-3"


def test_prepare_quarantines_v2_sidecar_without_reading_progress(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.workspace.sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest.workspace.manifest_path.write_text(
        json.dumps(
            {
                "version": 2,
                "signature": "sig-old",
                "segments": [
                    {
                        "index": 1,
                        "path": "segment_0001.mp4",
                        "start_output_frame": 0,
                        "end_output_frame": 999,
                        "frame_count": 1000,
                        "next_source_frame": 500,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (manifest.workspace.sidecar_dir / "segment_0001.mp4").write_bytes(b"v2-segment")

    decision = manifest.prepare("sig-old", {}, mode="auto")
    assert decision.kind == "fresh"
    payload = json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == _MANIFEST_VERSION
    chunks = [p for p in manifest.workspace.sidecar_dir.iterdir() if p.name.startswith("chunk-")]
    assert chunks == []
    backups = list(tmp_path.glob("out.mp4.vp_segments.incompatible*"))
    assert len(backups) == 1
    assert json.loads((backups[0] / "manifest.json").read_text(encoding="utf-8"))["version"] == 2
    assert (backups[0] / "segment_0001.mp4").read_bytes() == b"v2-segment"


def test_prepare_quarantines_corrupt_manifest(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.workspace.sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest.workspace.manifest_path.write_text("{not json", encoding="utf-8")
    stale_chunk = manifest.workspace.sidecar_dir / "chunk-tmp.mp4"
    stale_chunk.write_bytes(b"recoverable")

    decision = manifest.prepare("sig-new", {}, mode="auto")

    assert decision.kind == "fresh"
    backups = list(tmp_path.glob("out.mp4.vp_segments.incompatible*"))
    assert len(backups) == 1
    assert (backups[0] / "manifest.json").read_text(encoding="utf-8") == "{not json"
    assert (backups[0] / "chunk-tmp.mp4").read_bytes() == b"recoverable"


def test_prepare_quarantines_schema_three_manifest_with_missing_fields(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.workspace.sidecar_dir.mkdir(parents=True, exist_ok=True)
    incomplete = {
        "version": _MANIFEST_VERSION,
        "signature": "looks-current-but-is-incomplete",
    }
    manifest.workspace.manifest_path.write_text(json.dumps(incomplete), encoding="utf-8")
    stale_chunk = _make_chunk(
        manifest.workspace.sidecar_dir,
        index=1,
        start=0,
        end=99,
        next_src=50,
    )

    decision = manifest.prepare("looks-current-but-is-incomplete", {}, mode="auto")

    assert decision.kind == "fresh"
    backups = list(tmp_path.glob("out.mp4.vp_segments.incompatible*"))
    assert len(backups) == 1
    assert json.loads((backups[0] / "manifest.json").read_text(encoding="utf-8")) == incomplete
    assert (backups[0] / stale_chunk.name).is_file()


def test_scan_truncates_at_first_gap(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-4", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=999, next_src=500)
    # chunk 2 missing on purpose
    _make_chunk(manifest.workspace.sidecar_dir, index=3, start=2000, end=2999, next_src=1500)

    decision = manifest.prepare("sig-4", {}, mode="auto")
    assert decision.kind == "resume"
    assert [chunk.index for chunk in decision.state.completed_segments] == [1]
    # The orphan chunk-3 is removed by cleanup_stale_chunks during prepare.
    remaining = sorted(p.name for p in manifest.workspace.sidecar_dir.iterdir() if p.name.startswith("chunk-"))
    assert remaining == ["chunk-0001-out00000000-00000999-src00000500.mp4"]


def test_cleanup_partial_drops_in_flight_sentinel(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-5", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=999, next_src=500)
    sentinel = manifest.workspace.sidecar_dir / "chunk-tmp.mp4"
    sentinel.write_bytes(b"in-flight")

    decision = manifest.prepare("sig-5", {}, mode="auto")
    assert decision.kind == "resume"
    assert decision.state.completed_output_frames == 1000
    assert not sentinel.exists()


def test_prepare_auto_returns_conflict_when_final_exists(tmp_path):
    output = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig-conflict", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=999, next_src=500)
    output.write_bytes(b"final")

    decision = manifest.prepare("sig-conflict", {}, mode="auto")
    assert decision.kind == "conflict_final_exists"
    assert decision.sidecar_signature_match is True
    assert decision.state.completed_output_frames == 1000
    # no destructive action taken under auto mode
    assert output.exists()
    assert manifest.workspace.manifest_path.is_file()


def test_prepare_force_fresh_purges_final_and_sidecar(tmp_path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"final")
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig-7", {}, mode="auto")
    # the previous prepare returned a conflict but did not touch state; do it now
    decision = manifest.prepare("sig-7", {"foo": "bar"}, mode="force-fresh")
    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert not output.exists()
    payload = json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))
    assert payload["signature"] == "sig-7"
    assert payload["config_snapshot"] == {"foo": "bar"}


def test_prepare_force_fresh_with_changed_signature_also_purges_final(tmp_path):
    output = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig-old", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=99, next_src=50)
    output.write_bytes(b"stale-final")

    decision = manifest.prepare("sig-new", {"updated": True}, mode="force-fresh")

    assert decision.kind == "fresh"
    assert not output.exists()
    assert json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))["signature"] == "sig-new"
    backups = list(tmp_path.glob("out.mp4.vp_segments.incompatible*"))
    assert len(backups) == 1
    assert (backups[0] / "chunk-0001-out00000000-00000099-src00000050.mp4").is_file()


def test_prepare_fresh_fails_closed_when_sidecar_cleanup_fails(tmp_path, monkeypatch):
    output = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig", {"generation": 1}, mode="auto")
    output.write_bytes(b"existing-final")

    import app.planning.segment_workspace as segment_workspace

    def deny_cleanup(_path, *, ignore_errors=False):
        if ignore_errors:
            return
        raise PermissionError("sidecar is locked")

    monkeypatch.setattr(segment_workspace.shutil, "rmtree", deny_cleanup)

    with pytest.raises(PermissionError, match="sidecar is locked"):
        manifest.prepare("sig", {"generation": 2}, mode="force-fresh")

    assert output.read_bytes() == b"existing-final"
    payload = json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))
    assert payload["config_snapshot"] == {"generation": 1}


def test_prepare_fails_closed_when_stale_sentinel_cannot_be_removed(tmp_path, monkeypatch):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig", {}, mode="auto")
    sentinel = manifest.workspace.sidecar_dir / "chunk-tmp.mp4"
    sentinel.write_bytes(b"in-flight")
    real_unlink = Path.unlink

    def deny_sentinel_unlink(path: Path, *args, **kwargs):
        if path == sentinel:
            raise PermissionError("sentinel is locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_sentinel_unlink)

    with pytest.raises(PermissionError, match="sentinel is locked"):
        manifest.prepare("sig", {}, mode="auto")

    assert sentinel.read_bytes() == b"in-flight"


def test_prepare_fails_closed_when_noncontiguous_chunk_cannot_be_removed(tmp_path, monkeypatch):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=99, next_src=50)
    stale = _make_chunk(manifest.workspace.sidecar_dir, index=3, start=200, end=299, next_src=150)
    real_unlink = Path.unlink

    def deny_stale_unlink(path: Path, *args, **kwargs):
        if path == stale:
            raise PermissionError("stale chunk is locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_stale_unlink)

    with pytest.raises(PermissionError, match="stale chunk is locked"):
        manifest.prepare("sig", {}, mode="auto")

    assert stale.is_file()


def test_prepare_force_resume_reuses_matching_progress_with_final_output(tmp_path):
    output = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig-resume", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=99, next_src=50)
    output.write_bytes(b"previous-final")

    decision = manifest.prepare("sig-resume", {}, mode="force-resume")

    assert decision.kind == "resume"
    assert decision.sidecar_signature_match is True
    assert decision.state.completed_output_frames == 100
    assert output.read_bytes() == b"previous-final"


def test_prepare_force_resume_resets_mismatched_progress_without_deleting_final(tmp_path):
    output = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig-old", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=99, next_src=50)
    output.write_bytes(b"previous-final")

    decision = manifest.prepare("sig-new", {"updated": True}, mode="force-resume")

    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert output.read_bytes() == b"previous-final"
    payload = json.loads(manifest.workspace.manifest_path.read_text(encoding="utf-8"))
    assert payload["signature"] == "sig-new"
    assert payload["config_snapshot"] == {"updated": True}


def test_finalize_chunk_renames_atomically(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-8", {}, mode="auto")
    tmp_path_str = manifest.workspace.chunk_tmp_path(".mp4")
    Path(tmp_path_str).write_bytes(b"chunk-data")

    manifest.workspace.finalize_chunk(
        tmp_path_str,
        index=1,
        start_output_frame=0,
        end_output_frame=999,
        next_source_frame=500,
    )

    completed = manifest.scan_completed_chunks()
    assert len(completed) == 1
    final_path = manifest.workspace.sidecar_dir / completed[0].path
    assert final_path.is_file()
    assert not Path(tmp_path_str).exists()
    assert final_path.name == "chunk-0001-out00000000-00000999-src00000500.mp4"


def test_inspect_reports_sidecar_state(tmp_path):
    output = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output))
    manifest.prepare("sig-9", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=999, next_src=500)

    info = manifest.inspect("sig-9", total_output_frames=2000)
    assert info.final_exists is False
    assert info.sidecar_exists is True
    assert info.signature_match is True
    assert info.completed_chunks == 1
    assert info.completed_output_frames == 1000
    assert info.next_source_frame == 500
    assert info.total_output_frames == 2000


def test_inspect_does_not_mutate_noncontiguous_or_in_flight_chunks(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-read-only", {}, mode="auto")
    _make_chunk(manifest.workspace.sidecar_dir, index=1, start=0, end=99, next_src=50)
    stale = _make_chunk(manifest.workspace.sidecar_dir, index=3, start=200, end=299, next_src=150)
    sentinel = manifest.workspace.sidecar_dir / "chunk-tmp.mp4"
    sentinel.write_bytes(b"in-flight")
    before = {path.name: path.read_bytes() for path in manifest.workspace.sidecar_dir.iterdir()}

    info = manifest.inspect("sig-read-only", total_output_frames=300)

    after = {path.name: path.read_bytes() for path in manifest.workspace.sidecar_dir.iterdir()}
    assert info.completed_chunks == 1
    assert info.completed_output_frames == 100
    assert after == before
    assert stale.is_file()
    assert sentinel.is_file()


def test_inspect_handles_missing_sidecar(tmp_path):
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
    info = manifest.inspect("sig-10", total_output_frames=42)
    assert info.sidecar_exists is False
    assert info.signature_match is False
    assert info.completed_chunks == 0


def test_resume_conflict_error_serializes_details():
    err = ResumeConflictError(
        output_path="/tmp/x.mp4",
        completed_chunks=5,
        completed_output_frames=4999,
        sidecar_signature_match=True,
    )
    details = err.to_details()
    assert details == {
        "outputPath": "/tmp/x.mp4",
        "completedChunks": 5,
        "completedOutputFrames": 4999,
        "sidecarSignatureMatch": True,
    }


def test_manifest_write_uses_tmp_then_replace(tmp_path, monkeypatch):
    """The manifest writer should always go via a .tmp + os.replace dance."""
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))

    captured: list[tuple[str, str]] = []

    import app.planning.manifest_store as manifest_store

    real_replace = manifest_store.os.replace

    def tracking_replace(src, dst):
        captured.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(manifest_store.os, "replace", tracking_replace)

    decision = manifest.prepare("sig-a", {}, mode="auto")
    assert decision.kind == "fresh"
    assert captured, "manifest write must invoke os.replace"
    src, dst = captured[-1]
    assert dst == str(manifest.workspace.manifest_path)
    assert src.startswith(dst) or src.endswith(".tmp")
    assert manifest.workspace.manifest_path.is_file()
