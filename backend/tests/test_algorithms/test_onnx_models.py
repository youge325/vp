from pathlib import Path

import pytest

from app.algorithms.onnx_models import (
    is_safe_onnx_filename,
    resolve_onnx_model_path,
    scan_onnx_models,
)


def test_scan_onnx_models_uses_expected_subdirectories(tmp_path: Path):
    interpolation = tmp_path / "interpolation"
    super_resolution = tmp_path / "super_resolution"
    interpolation.mkdir()
    super_resolution.mkdir()
    (interpolation / "b.onnx").write_bytes(b"model")
    (interpolation / "a.ONNX").write_bytes(b"model")
    (interpolation / "empty.onnx").write_bytes(b"")
    (interpolation / "notes.txt").write_text("skip", encoding="utf-8")
    (super_resolution / "sr.onnx").write_bytes(b"model")

    assert scan_onnx_models(tmp_path) == {
        "interpolation": ["a.ONNX", "b.onnx"],
        "super_resolution": ["sr.onnx"],
    }


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.onnx",
        "..\\escape.onnx",
        "C:\\model.onnx",
        "/tmp/model.onnx",
        "model.pkl",
        "",
    ],
)
def test_rejects_non_basename_onnx_filenames(filename: str):
    assert is_safe_onnx_filename(filename) is False


def test_resolve_onnx_model_path_rejects_missing_or_unsafe_files(tmp_path: Path):
    model_dir = tmp_path / "interpolation"
    model_dir.mkdir()
    (model_dir / "model.onnx").write_bytes(b"model")

    assert resolve_onnx_model_path("interpolation", "model.onnx", tmp_path) == model_dir / "model.onnx"
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", "../model.onnx", tmp_path)
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", "missing.onnx", tmp_path)
