"""Release-model preparation fails closed and emits inference-only assets."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import prepare_real_rawvsr_models as preparation  # noqa: E402


def _write_manifest(root: Path, *, source_bytes: int, source_sha256: str) -> Path:
    license_dir = root / "licenses/real-rawvsr"
    license_dir.mkdir(parents=True)
    (license_dir / "CC-BY-NC-SA-4.0.txt").write_text("license", encoding="utf-8")
    (license_dir / "NOTICE.md").write_text("notice", encoding="utf-8")
    (license_dir / "THIRD-PARTY-NOTICES.md").write_text("third party", encoding="utf-8")
    manifest = {
        "license": {
            "licenseRelativePath": "licenses/real-rawvsr/CC-BY-NC-SA-4.0.txt",
            "noticeRelativePath": "licenses/real-rawvsr/NOTICE.md",
            "thirdPartyNoticeRelativePath": "licenses/real-rawvsr/THIRD-PARTY-NOTICES.md",
        },
        "families": [
            {
                "algorithmId": "real-rawvsr-basicvsr",
                "upstreamCheckpoint": {
                    "folder": "model_BasicVSR",
                    "sourceStem": "basicvsr",
                },
                "variants": [
                    {
                        "scaleFactor": 2,
                        "googleDriveFileId": "official-x2",
                        "sourceBytes": source_bytes,
                        "sourceSha256": source_sha256,
                        "inferenceBytes": 1,
                        "inferenceSha256": "0" * 64,
                        "parameterCount": 1,
                        "relativePath": "models/super_resolution/pytorch/real-rawvsr-basicvsr/x2/model.safetensors",
                    }
                ],
            }
        ],
    }
    path = root / "contracts/model-assets.json"
    path.parent.mkdir()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_model_preparation_requires_explicit_noncommercial_acceptance() -> None:
    with pytest.raises(RuntimeError, match="requires --accept-noncommercial"):
        preparation.prepare_models(acceptance="")


def test_model_preparation_rejects_source_hash_drift_before_loading_pickle(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source/real-rawvsr-basicvsr/x2/best.pth"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not-an-official-checkpoint")
    manifest_path = _write_manifest(
        tmp_path,
        source_bytes=source.stat().st_size,
        source_sha256="0" * 64,
    )
    monkeypatch.setattr(preparation, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preparation, "ASSET_MANIFEST", manifest_path)

    with pytest.raises(RuntimeError, match="official checkpoint SHA-256 mismatch"):
        preparation.prepare_models(
            acceptance="CC-BY-NC-SA-4.0-NONCOMMERCIAL",
            source_dir=source.parents[2],
        )

    assert not any((tmp_path / "backend").rglob("*.safetensors"))


def test_model_preparation_propagates_download_failure_without_partial_output(tmp_path: Path, monkeypatch) -> None:
    manifest_path = _write_manifest(tmp_path, source_bytes=1, source_sha256="0" * 64)
    monkeypatch.setattr(preparation, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preparation, "ASSET_MANIFEST", manifest_path)

    def fail_download(_file_id: str, _destination: Path) -> None:
        raise OSError("download unavailable")

    monkeypatch.setattr(preparation, "_download_google_drive", fail_download)

    with pytest.raises(OSError, match="download unavailable"):
        preparation.prepare_models(acceptance="CC-BY-NC-SA-4.0-NONCOMMERCIAL")

    assert not any((tmp_path / "backend").rglob("*"))


def test_model_preparation_requires_packaged_license_files(tmp_path: Path, monkeypatch) -> None:
    manifest_path = _write_manifest(tmp_path, source_bytes=1, source_sha256="0" * 64)
    (tmp_path / "licenses/real-rawvsr/NOTICE.md").unlink()
    monkeypatch.setattr(preparation, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preparation, "ASSET_MANIFEST", manifest_path)

    with pytest.raises(RuntimeError, match="license file is missing"):
        preparation.prepare_models(acceptance="CC-BY-NC-SA-4.0-NONCOMMERCIAL")


def test_runtime_tools_integrity_port_accepts_exact_file_and_rejects_drift(tmp_path: Path) -> None:
    asset = tmp_path / "model.safetensors"
    asset.write_bytes(b"safe")
    digest = hashlib.sha256(b"safe").hexdigest()
    helper = SCRIPTS_DIR / "runtime-tools.ps1"
    command = (
        f". '{helper}'; "
        f"Assert-VpFileIntegrity -Path '{asset}' -ExpectedBytes 4 -ExpectedSha256 '{digest}' -Label model | Out-Null"
    )
    valid = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert valid.returncode == 0, valid.stderr

    drifted = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command.replace(digest, "0" * 64)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert drifted.returncode != 0
    assert "SHA-256 mismatch" in drifted.stderr
