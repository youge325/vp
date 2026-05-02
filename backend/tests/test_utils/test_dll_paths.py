"""Tests for ``app.utils.dll_paths``."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.utils import dll_paths


@pytest.fixture(autouse=True)
def _reset_registry():
    dll_paths.reset_registry_for_tests()
    yield
    dll_paths.reset_registry_for_tests()


def test_register_native_dll_paths_is_noop_off_windows(monkeypatch):
    monkeypatch.setattr(dll_paths.sys, "platform", "linux")
    assert dll_paths.register_native_dll_paths() == []


def test_registers_tensorrt_bin_when_dir_exists(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):  # pragma: no cover - covered indirectly
        pytest.skip("Windows-only behaviour")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", str(tmp_path))
    monkeypatch.delenv("CUDA_PATH", raising=False)

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    registered = dll_paths.register_native_dll_paths()
    assert [Path(p) for p in captured] == [bin_dir.resolve()]
    assert registered == [bin_dir.resolve()]


def test_double_registration_is_idempotent(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", str(tmp_path))
    monkeypatch.delenv("CUDA_PATH", raising=False)

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()
    second = dll_paths.register_native_dll_paths()
    assert second == []  # already registered
    assert len(captured) == 1


def test_missing_bin_subdir_warns_but_does_not_raise(tmp_path: Path, monkeypatch, caplog):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", str(tmp_path))
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", lambda _path: None)

    with caplog.at_level("WARNING"):
        registered = dll_paths.register_native_dll_paths()

    assert registered == []
    assert any("does not contain a 'bin'" in r.message for r in caplog.records)


def test_unset_tensorrt_dir_skips_silently(monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", "")
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    assert dll_paths.register_native_dll_paths() == []
    assert captured == []


def test_picks_up_cuda_path_when_present(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", "")
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])
    cuda_root = tmp_path / "cuda"
    cuda_bin = cuda_root / "bin"
    cuda_bin.mkdir(parents=True)
    monkeypatch.setenv("CUDA_PATH", str(cuda_root))

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    registered = dll_paths.register_native_dll_paths()
    assert [Path(p) for p in captured] == [cuda_bin.resolve()]
    assert registered == [cuda_bin.resolve()]


def test_extra_paths_are_registered_after_settings(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", "")
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    registered = dll_paths.register_native_dll_paths(extra=[extra_dir])
    assert [Path(p) for p in captured] == [extra_dir.resolve()]
    assert registered == [extra_dir.resolve()]


def test_registers_directory_into_path_for_legacy_loader(tmp_path: Path, monkeypatch):
    """ONNX Runtime's TRT provider DLL resolves nvinfer_10.dll via the legacy
    LoadLibrary search order, which only honours PATH (not AddDllDirectory).
    register_native_dll_paths must therefore prepend the directory to PATH so
    transitive DLL imports resolve."""
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setattr(dll_paths.settings, "TENSORRT_DIR", str(tmp_path))
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setenv("PATH", "C:\\some\\dir;C:\\other")
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", lambda _path: None)

    dll_paths.register_native_dll_paths()

    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0].lower() == str(bin_dir.resolve()).lower(), (
        f"expected bin dir to be the first PATH entry, got {parts!r}"
    )
