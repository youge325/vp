from pathlib import Path

import pytest

from app.utils.onnx_models import (
    create_onnx_session,
    is_safe_onnx_filename,
    resolve_onnx_model_path,
    scan_onnx_models,
    select_onnx_providers,
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


class _StubOrt:
    def __init__(self, available: list[str], bound_override: list[str] | None = None):
        self._available = list(available)
        self._bound_override = bound_override

    def get_available_providers(self) -> list[str]:
        return list(self._available)

    class _Session:
        def __init__(self, path, providers, bound_override):
            self.path = path
            self.providers = list(providers)
            self._bound = list(bound_override) if bound_override is not None else list(providers)

        def get_providers(self) -> list[str]:
            return list(self._bound)

    def InferenceSession(self, path, providers):  # noqa: N802 - matches onnxruntime API
        return self._Session(path, providers, self._bound_override)


def test_select_onnx_providers_returns_strict_priority_when_available():
    ort = _StubOrt(["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"])
    assert select_onnx_providers("tensorrt", ort) == [
        "TensorrtExecutionProvider",
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_select_onnx_providers_drops_missing_secondary_providers_with_warning():
    ort = _StubOrt(["CUDAExecutionProvider", "CPUExecutionProvider"])
    selected = select_onnx_providers("cuda", ort)
    assert selected == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_select_onnx_providers_raises_when_primary_missing():
    ort = _StubOrt(["CPUExecutionProvider"])
    with pytest.raises(RuntimeError, match="CUDAExecutionProvider"):
        select_onnx_providers("cuda", ort)
    with pytest.raises(RuntimeError, match="TensorrtExecutionProvider"):
        select_onnx_providers("tensorrt", ort)


def test_select_onnx_providers_auto_passes_through_available():
    ort = _StubOrt(["CPUExecutionProvider"])
    assert select_onnx_providers("auto", ort) == ["CPUExecutionProvider"]


def test_create_onnx_session_warns_when_session_falls_back_to_cpu(caplog: pytest.LogCaptureFixture):
    # Provider IS reachable, so selection succeeds, but the actual session
    # only manages to bind CPU — that's the silent-fallback case we want to flag.
    ort = _StubOrt(
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
        bound_override=["CPUExecutionProvider"],
    )
    with caplog.at_level("WARNING"):
        session = create_onnx_session("/tmp/model.onnx", engine="cuda", ort_module=ort)
    assert session.get_providers() == ["CPUExecutionProvider"]
    fallback_messages = [record.message for record in caplog.records if "fell back" in record.message]
    assert fallback_messages, "expected a fall-back warning"


def test_create_onnx_session_quiet_when_primary_provider_binds(caplog: pytest.LogCaptureFixture):
    ort = _StubOrt(["CUDAExecutionProvider", "CPUExecutionProvider"])
    with caplog.at_level("WARNING"):
        session = create_onnx_session("/tmp/model.onnx", engine="cuda", ort_module=ort)
    assert session.get_providers()[0] == "CUDAExecutionProvider"
    fallback_messages = [record.message for record in caplog.records if "fell back" in record.message]
    assert fallback_messages == []
