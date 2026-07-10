"""Focused tests for resume manifest JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.planning.manifest_store as manifest_store


@pytest.mark.parametrize(
    "contents",
    [
        "{not json",
        json.dumps({"version": manifest_store.MANIFEST_VERSION - 1, "signature": "old"}),
        json.dumps(["not", "an", "object"]),
    ],
)
def test_load_manifest_rejects_invalid_payloads(tmp_path: Path, contents: str) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(contents, encoding="utf-8")

    assert manifest_store.load_manifest(manifest_path) is None


def test_write_manifest_uses_atomic_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = tmp_path / "segments" / "manifest.json"
    output_path = tmp_path / "output.mp4"
    captured: list[tuple[str, str]] = []
    real_replace = manifest_store.os.replace

    def tracking_replace(src: str | Path, dst: str | Path) -> None:
        captured.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(manifest_store.os, "replace", tracking_replace)

    manifest_store.write_manifest(
        manifest_path,
        signature="sig-a",
        output_path=output_path,
        config_snapshot={"input_path": "input.mp4", "quality": 18},
    )

    assert captured == [(str(manifest_path.with_suffix(".json.tmp")), str(manifest_path))]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload == {
        "version": manifest_store.MANIFEST_VERSION,
        "signature": "sig-a",
        "created_at": payload["created_at"],
        "input_path": "input.mp4",
        "output_path": str(output_path),
        "config_snapshot": {"input_path": "input.mp4", "quality": 18},
    }
    assert payload["created_at"].endswith("Z")
    assert not manifest_path.with_suffix(".json.tmp").exists()
