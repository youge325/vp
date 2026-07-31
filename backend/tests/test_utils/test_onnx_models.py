from pathlib import Path

import pytest

from app.utils.onnx_models import (
    create_onnx_session,
    resolve_onnx_model_path,
    scan_onnx_catalog,
)


def test_scan_onnx_catalog_groups_by_algorithm_subdirectory(tmp_path: Path):
    interp_rife = tmp_path / "interpolation" / "rife"
    interp_rife.mkdir(parents=True)
    (interp_rife / "b.onnx").write_bytes(b"model")
    (interp_rife / "a.ONNX").write_bytes(b"model")
    (interp_rife / "empty.onnx").write_bytes(b"")
    (interp_rife / "notes.txt").write_text("skip", encoding="utf-8")
    # Loose .onnx file directly under <kind>/ (no algorithm subdir) must be ignored.
    (tmp_path / "interpolation" / "stray.onnx").write_bytes(b"model")

    sr_alg = tmp_path / "super_resolution" / "realesrgan"
    sr_alg.mkdir(parents=True)
    (sr_alg / "sr.onnx").write_bytes(b"model")

    catalog = scan_onnx_catalog(tmp_path)
    assert catalog.names == {
        "interpolation": {"rife": ["a.ONNX", "b.onnx"]},
        "super_resolution": {"realesrgan": ["sr.onnx"]},
    }
    assert [detail.name for detail in catalog.details["interpolation"]["rife"]] == ["a.ONNX", "b.onnx"]


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.onnx",
        "..\\escape.onnx",
        "C:\\model.onnx",
        "/tmp/model.onnx",
        "rife/model.onnx",
        "model.pkl",
        "",
    ],
)
def test_rejects_non_basename_onnx_filenames(tmp_path: Path, filename: str):
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", "rife", filename, tmp_path)


@pytest.mark.parametrize(
    "name",
    [
        "../rife",
        "rife/sub",
        "rife\\sub",
        "",
        ".",
        "..",
    ],
)
def test_rejects_unsafe_algorithm_names(tmp_path: Path, name: str):
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", name, "model.onnx", tmp_path)


def test_resolve_onnx_model_path_rejects_missing_or_unsafe_files(tmp_path: Path):
    model_dir = tmp_path / "interpolation" / "rife"
    model_dir.mkdir(parents=True)
    (model_dir / "model.onnx").write_bytes(b"model")

    assert resolve_onnx_model_path("interpolation", "rife", "model.onnx", tmp_path) == model_dir / "model.onnx"
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", "rife", "../model.onnx", tmp_path)
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", "rife", "missing.onnx", tmp_path)
    with pytest.raises(FileNotFoundError):
        resolve_onnx_model_path("interpolation", "../rife", "model.onnx", tmp_path)


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


def test_create_onnx_session_uses_strict_provider_priority():
    ort = _StubOrt(["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"])
    session = create_onnx_session("/tmp/model.onnx", engine="tensorrt", ort_module=ort)
    assert session.providers == [
        "TensorrtExecutionProvider",
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_create_onnx_session_uses_available_cuda_provider_chain():
    ort = _StubOrt(["CUDAExecutionProvider", "CPUExecutionProvider"])
    session = create_onnx_session("/tmp/model.onnx", engine="cuda", ort_module=ort)
    assert session.providers == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_create_onnx_session_raises_when_primary_provider_is_missing():
    ort = _StubOrt(["CPUExecutionProvider"])
    with pytest.raises(RuntimeError, match="CUDAExecutionProvider"):
        create_onnx_session("/tmp/model.onnx", engine="cuda", ort_module=ort)
    with pytest.raises(RuntimeError, match="TensorrtExecutionProvider"):
        create_onnx_session("/tmp/model.onnx", engine="tensorrt", ort_module=ort)


@pytest.mark.parametrize("engine", ["auto", "dcu"])
def test_create_onnx_session_rejects_unsupported_engine(engine: str):
    ort = _StubOrt(["CPUExecutionProvider"])
    with pytest.raises(ValueError, match="Unsupported ONNX inference engine"):
        create_onnx_session("/tmp/model.onnx", engine=engine, ort_module=ort)


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
