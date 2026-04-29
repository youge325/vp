"""ONNX model discovery and safe path resolution."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from app.config import settings

OnnxModelKind = Literal["interpolation", "super_resolution"]

ONNX_MODEL_SUBDIRS: dict[OnnxModelKind, str] = {
    "interpolation": "interpolation",
    "super_resolution": "super_resolution",
}


def get_onnx_model_dir(kind: OnnxModelKind, model_root: str | Path | None = None) -> Path:
    """Return the configured ONNX model directory for a model kind."""
    root = Path(model_root or settings.RIFE_MODEL_DIR).expanduser().resolve()
    return root / ONNX_MODEL_SUBDIRS[kind]


def scan_onnx_models(model_root: str | Path | None = None) -> dict[str, list[str]]:
    """List available ONNX model filenames by supported video model kind."""
    return {kind: _scan_dir(get_onnx_model_dir(kind, model_root)) for kind in ONNX_MODEL_SUBDIRS}


def resolve_onnx_model_path(
    kind: OnnxModelKind,
    filename: str | None,
    model_root: str | Path | None = None,
) -> Path:
    """Resolve a frontend-supplied ONNX filename inside the expected model subdir."""
    if not filename or not is_safe_onnx_filename(filename):
        raise FileNotFoundError(f"Invalid ONNX model filename: {filename or '<empty>'}")

    model_dir = get_onnx_model_dir(kind, model_root)
    candidate = (model_dir / filename).resolve()
    model_dir_resolved = model_dir.resolve()

    try:
        candidate.relative_to(model_dir_resolved)
    except ValueError as exc:
        raise FileNotFoundError(f"ONNX model path escapes the model directory: {filename}") from exc

    if not candidate.is_file() or candidate.stat().st_size <= 0:
        raise FileNotFoundError(f"ONNX model file not found: {candidate}")
    return candidate


def is_safe_onnx_filename(filename: str) -> bool:
    """Return True when filename is a basename-only .onnx file reference."""
    if filename in {"", ".", ".."}:
        return False
    if PurePosixPath(filename).name != filename:
        return False

    windows_path = PureWindowsPath(filename)
    if windows_path.name != filename or windows_path.drive or windows_path.root:
        return False

    return filename.lower().endswith(".onnx")


def _scan_dir(model_dir: Path) -> list[str]:
    if not model_dir.is_dir():
        return []
    return sorted(
        (
            item.name
            for item in model_dir.iterdir()
            if item.is_file()
            and item.suffix.lower() == ".onnx"
            and item.stat().st_size > 0
            and is_safe_onnx_filename(item.name)
        ),
        key=str.casefold,
    )
