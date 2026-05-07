"""Unit tests for the filesystem-as-state SegmentManifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.errors import ResumeConflictError
from app.processing.streaming import SegmentManifest


def _workspace(name: str) -> Path:
    root = Path("D:/Lenovo/vp/.tmp/test_segment_manifest") / name
    if root.exists():
        import shutil

        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _make_chunk(sidecar: Path, *, index: int, start: int, end: int, next_src: int) -> Path:
    name = f"chunk-{index:04d}-out{start:08d}-{end:08d}-src{next_src:08d}.mp4"
    path = sidecar / name
    path.write_bytes(b"chunk")
    return path


def test_prepare_fresh_when_sidecar_missing(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    decision = manifest.prepare("sig-1", {"foo": "bar"}, mode="auto")

    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert decision.state.start_source_frame == 0
    assert decision.state.completed_segments == []
    assert manifest.manifest_path.is_file()
    payload = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == SegmentManifest.MANIFEST_VERSION
    assert payload["signature"] == "sig-1"
    assert payload["config_snapshot"] == {"foo": "bar"}
    assert "segments" not in payload  # progress is filesystem-derived


def test_prepare_resume_with_contiguous_chunks(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-2", {}, mode="auto")
    _make_chunk(manifest.sidecar_dir, index=1, start=0, end=999, next_src=500)
    _make_chunk(manifest.sidecar_dir, index=2, start=1000, end=1499, next_src=750)

    decision = manifest.prepare("sig-2", {}, mode="auto")
    assert decision.kind == "resume"
    assert decision.state.completed_output_frames == 1500
    assert decision.state.start_source_frame == 750
    assert [chunk.index for chunk in decision.state.completed_segments] == [1, 2]


def test_prepare_resets_on_signature_mismatch(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-old", {}, mode="auto")
    _make_chunk(manifest.sidecar_dir, index=1, start=0, end=999, next_src=500)

    decision = manifest.prepare("sig-new", {}, mode="auto")
    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert manifest.manifest_path.is_file()
    chunks = list(p.name for p in manifest.sidecar_dir.iterdir() if p.name.startswith("chunk-"))
    assert chunks == []


def test_prepare_recovers_from_corrupt_manifest(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest.manifest_path.write_text("{not json", encoding="utf-8")

    decision = manifest.prepare("sig-3", {}, mode="auto")
    assert decision.kind == "fresh"
    assert manifest.manifest_path.is_file()
    payload = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert payload["signature"] == "sig-3"


def test_prepare_drops_v1_sidecar(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest.manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
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
    (manifest.sidecar_dir / "segment_0001.mp4").write_bytes(b"v1-segment")

    decision = manifest.prepare("sig-old", {}, mode="auto")
    assert decision.kind == "fresh"
    payload = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == SegmentManifest.MANIFEST_VERSION
    chunks = [p for p in manifest.sidecar_dir.iterdir() if p.name.startswith("chunk-")]
    assert chunks == []
    assert not (manifest.sidecar_dir / "segment_0001.mp4").exists()


def test_scan_truncates_at_first_gap(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-4", {}, mode="auto")
    _make_chunk(manifest.sidecar_dir, index=1, start=0, end=999, next_src=500)
    # chunk 2 missing on purpose
    _make_chunk(manifest.sidecar_dir, index=3, start=2000, end=2999, next_src=1500)

    decision = manifest.prepare("sig-4", {}, mode="auto")
    assert decision.kind == "resume"
    assert [chunk.index for chunk in decision.state.completed_segments] == [1]
    # The orphan chunk-3 is removed by cleanup_stale_chunks during prepare.
    remaining = sorted(p.name for p in manifest.sidecar_dir.iterdir() if p.name.startswith("chunk-"))
    assert remaining == ["chunk-0001-out00000000-00000999-src00000500.mp4"]


def test_cleanup_partial_drops_in_flight_sentinel(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-5", {}, mode="auto")
    _make_chunk(manifest.sidecar_dir, index=1, start=0, end=999, next_src=500)
    sentinel = manifest.sidecar_dir / "chunk-tmp.mp4"
    sentinel.write_bytes(b"in-flight")

    decision = manifest.prepare("sig-5", {}, mode="auto")
    assert decision.kind == "resume"
    assert decision.state.completed_output_frames == 1000
    assert not sentinel.exists()


def test_prepare_auto_returns_conflict_when_final_exists(tmp_path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"final")
    manifest = SegmentManifest(str(output))
    # pre-existing matching sidecar
    manifest.sidecar_dir.mkdir(parents=True, exist_ok=True)
    manifest.manifest_path.write_text(
        json.dumps(
            {
                "version": SegmentManifest.MANIFEST_VERSION,
                "signature": "sig-conflict",
                "config_snapshot": {},
            }
        ),
        encoding="utf-8",
    )
    _make_chunk(manifest.sidecar_dir, index=1, start=0, end=999, next_src=500)

    decision = manifest.prepare("sig-conflict", {}, mode="auto")
    assert decision.kind == "conflict_final_exists"
    assert decision.sidecar_signature_match is True
    assert decision.state.completed_output_frames == 1000
    # no destructive action taken under auto mode
    assert output.exists()
    assert manifest.manifest_path.is_file()


def test_prepare_force_fresh_purges_final_and_sidecar(tmp_path):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"final")
    manifest = SegmentManifest(str(output))
    manifest.prepare("sig-7", {}, mode="auto")
    # the previous prepare returned a conflict but did not touch state; do it now
    decision = manifest.prepare("sig-7", {"foo": "bar"}, mode="force-fresh")
    assert decision.kind == "fresh"
    assert decision.state.completed_output_frames == 0
    assert not output.exists()
    payload = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    assert payload["signature"] == "sig-7"
    assert payload["config_snapshot"] == {"foo": "bar"}


def test_finalize_chunk_renames_atomically(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    manifest.prepare("sig-8", {}, mode="auto")
    tmp_path_str = manifest.chunk_tmp_path(".mp4")
    Path(tmp_path_str).write_bytes(b"chunk-data")

    final_path = manifest.finalize_chunk(
        tmp_path_str,
        index=1,
        start_output_frame=0,
        end_output_frame=999,
        next_source_frame=500,
    )

    assert Path(final_path).is_file()
    assert not Path(tmp_path_str).exists()
    assert Path(final_path).name == "chunk-0001-out00000000-00000999-src00000500.mp4"


def test_inspect_reports_sidecar_state(tmp_path):
    output = tmp_path / "out.mp4"
    manifest = SegmentManifest(str(output))
    manifest.prepare("sig-9", {}, mode="auto")
    _make_chunk(manifest.sidecar_dir, index=1, start=0, end=999, next_src=500)

    info = manifest.inspect("sig-9", total_output_frames=2000)
    assert info["finalExists"] is False
    assert info["sidecarExists"] is True
    assert info["signatureMatch"] is True
    assert info["completedChunks"] == 1
    assert info["completedOutputFrames"] == 1000
    assert info["nextSourceFrame"] == 500
    assert info["totalOutputFrames"] == 2000


def test_inspect_handles_missing_sidecar(tmp_path):
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    info = manifest.inspect("sig-10", total_output_frames=42)
    assert info["sidecarExists"] is False
    assert info["signatureMatch"] is False
    assert info["completedChunks"] == 0


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
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))

    captured: list[tuple[str, str]] = []

    import app.planning as planning_module

    real_replace = planning_module.os.replace

    def tracking_replace(src, dst):
        captured.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(planning_module.os, "replace", tracking_replace)

    decision = manifest.prepare("sig-a", {}, mode="auto")
    assert decision.kind == "fresh"
    assert captured, "manifest write must invoke os.replace"
    src, dst = captured[-1]
    assert dst == str(manifest.manifest_path)
    assert src.startswith(dst) or src.endswith(".tmp")
    assert manifest.manifest_path.is_file()
