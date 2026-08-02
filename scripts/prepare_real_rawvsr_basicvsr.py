"""Download, verify, and deterministically convert official BasicVSR weights."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_MANIFEST = REPO_ROOT / "contracts/model-assets.json"
_LICENSE_ACCEPTANCE = "CC-BY-NC-SA-4.0-NONCOMMERCIAL"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify(path: Path, *, expected_bytes: int, expected_sha256: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label} is missing: {path}")
    actual_bytes = path.stat().st_size
    if actual_bytes != expected_bytes:
        raise RuntimeError(f"{label} size mismatch: expected {expected_bytes}, got {actual_bytes} ({path})")
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"{label} SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256} ({path})")


def _download_google_drive(file_id: str, destination: Path) -> None:
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    request = urllib.request.Request(url, headers={"User-Agent": "VP-Workbench-model-builder/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)


def _source_checkpoint(source_dir: Path | None, scale_factor: int, temporary_dir: Path) -> Path:
    if source_dir is None:
        return temporary_dir / f"basicvsr-x{scale_factor}-best.pth"
    candidates = (
        source_dir / f"x{scale_factor}" / "best.pth",
        source_dir / f"BasicVSR_{scale_factor}X" / "best.pth",
        source_dir / f"basicvsr-x{scale_factor}-best.pth",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        f"No x{scale_factor} source checkpoint found under {source_dir}; expected one of "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _serialize_state_dict(checkpoint_path: Path) -> bytes:
    import torch
    from safetensors.torch import save

    checkpoint: Any = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("state_dict"), dict):
        raise RuntimeError(f"Official checkpoint has no state_dict mapping: {checkpoint_path}")
    state_dict = checkpoint["state_dict"]
    if not state_dict or any(
        not isinstance(name, str) or not torch.is_tensor(value) for name, value in state_dict.items()
    ):
        raise RuntimeError(f"Official checkpoint state_dict contains unsupported entries: {checkpoint_path}")
    tensors = {name: tensor.detach().cpu().contiguous() for name, tensor in state_dict.items()}
    first = save(tensors, metadata={"format": "pt"})
    second = save(tensors, metadata={"format": "pt"})
    if first != second:
        raise RuntimeError(f"SafeTensors conversion is not deterministic: {checkpoint_path}")
    return first


def prepare_models(*, acceptance: str, source_dir: Path | None = None) -> None:
    if acceptance != _LICENSE_ACCEPTANCE:
        raise RuntimeError(
            "Model preparation requires --accept-noncommercial "
            f"{_LICENSE_ACCEPTANCE}; the weights may not be used commercially."
        )
    manifest = json.loads(ASSET_MANIFEST.read_text(encoding="utf-8"))["realRawVsrBasicVsr"]
    license_info = manifest["license"]
    for field in ("noticeRelativePath", "licenseRelativePath"):
        license_path = REPO_ROOT / license_info[field]
        if not license_path.is_file() or license_path.stat().st_size == 0:
            raise RuntimeError(f"Required model license file is missing: {license_path}")

    with tempfile.TemporaryDirectory(prefix="vp-real-rawvsr-") as temporary:
        temporary_dir = Path(temporary)
        for variant in manifest["variants"]:
            scale_factor = int(variant["scaleFactor"])
            output_path = REPO_ROOT / "backend" / variant["relativePath"]
            if output_path.is_file():
                _verify(
                    output_path,
                    expected_bytes=int(variant["inferenceBytes"]),
                    expected_sha256=str(variant["inferenceSha256"]),
                    label=f"x{scale_factor} inference model",
                )
                continue
            source_path = _source_checkpoint(source_dir, scale_factor, temporary_dir)
            if source_dir is None:
                _download_google_drive(str(variant["googleDriveFileId"]), source_path)
            _verify(
                source_path,
                expected_bytes=int(variant["sourceBytes"]),
                expected_sha256=str(variant["sourceSha256"]),
                label=f"x{scale_factor} official checkpoint",
            )
            converted = _serialize_state_dict(source_path)
            if len(converted) != int(variant["inferenceBytes"]):
                raise RuntimeError(
                    f"x{scale_factor} SafeTensors size mismatch: "
                    f"expected {variant['inferenceBytes']}, got {len(converted)}"
                )
            converted_sha256 = hashlib.sha256(converted).hexdigest()
            if converted_sha256 != variant["inferenceSha256"]:
                raise RuntimeError(
                    f"x{scale_factor} SafeTensors SHA-256 mismatch: "
                    f"expected {variant['inferenceSha256']}, got {converted_sha256}"
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_output = output_path.with_suffix(".safetensors.tmp")
            try:
                temporary_output.write_bytes(converted)
                temporary_output.replace(output_path)
            finally:
                temporary_output.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accept-noncommercial", default="")
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    prepare_models(acceptance=args.accept_noncommercial, source_dir=args.source_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
