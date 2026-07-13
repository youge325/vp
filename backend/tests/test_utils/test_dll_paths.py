"""Tests for ``app.utils.dll_paths``."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.utils import dll_paths

_ORIGINAL_PYTHON_PACKAGE_DLL_DIRS = dll_paths._python_package_dll_dirs


@pytest.fixture(autouse=True)
def _reset_registry(monkeypatch):
    monkeypatch.setattr(dll_paths, "_registered", set())
    monkeypatch.setattr(dll_paths, "_scanned_tensorrt_roots", None)
    monkeypatch.delenv("VP_OPENCV_BIN_DIR", raising=False)
    monkeypatch.delenv("VP_OPENCV_DIR", raising=False)
    monkeypatch.setattr(dll_paths, "_python_package_dll_dirs", lambda: [], raising=False)


def test_register_native_dll_paths_is_noop_off_windows(monkeypatch):
    monkeypatch.setattr(dll_paths.sys, "platform", "linux")
    dll_paths.register_native_dll_paths()

    assert dll_paths._registered == set()


def test_registers_tensorrt_bin_when_dir_exists(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):  # pragma: no cover - covered indirectly
        pytest.skip("Windows-only behaviour")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.delenv("CUDA_PATH", raising=False)

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths(tensorrt_dir=str(tmp_path))

    assert [Path(p) for p in captured] == [bin_dir.resolve()]


def test_double_registration_is_idempotent(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.delenv("CUDA_PATH", raising=False)

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths(tensorrt_dir=str(tmp_path))
    dll_paths.register_native_dll_paths(tensorrt_dir=str(tmp_path))

    assert len(captured) == 1


def test_missing_bin_subdir_warns_but_does_not_raise(tmp_path: Path, monkeypatch, caplog):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", lambda _path: None)

    with caplog.at_level("WARNING"):
        dll_paths.register_native_dll_paths(tensorrt_dir=str(tmp_path))

    assert dll_paths._registered == set()
    assert any("does not contain a 'bin'" in r.message for r in caplog.records)


def test_unset_tensorrt_dir_skips_silently(monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()

    assert captured == []


def test_registers_pip_tensorrt_package_dll_dirs(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    trt_libs = tmp_path / "tensorrt_libs"
    trt_rtx_libs = tmp_path / "tensorrt_rtx_libs"
    torch_trt_lib = tmp_path / "torch_tensorrt" / "lib"
    trt_libs.mkdir()
    trt_rtx_libs.mkdir()
    torch_trt_lib.mkdir(parents=True)
    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])
    monkeypatch.setattr(
        dll_paths,
        "_python_package_dll_dirs",
        lambda: [trt_libs, trt_rtx_libs, torch_trt_lib],
        raising=False,
    )

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()

    assert [Path(p) for p in captured] == [trt_libs.resolve(), trt_rtx_libs.resolve(), torch_trt_lib.resolve()]


def test_pip_tensorrt_dirs_skip_auto_discovered_roots(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    auto_root = tmp_path / "TensorRT-10" / "bin"
    trt_libs = tmp_path / "site-packages" / "tensorrt_libs"
    auto_root.mkdir(parents=True)
    trt_libs.mkdir(parents=True)
    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [auto_root])
    monkeypatch.setattr(dll_paths, "_python_package_dll_dirs", lambda: [trt_libs])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()

    assert [Path(p) for p in captured] == [trt_libs.resolve()]


def test_python_package_dll_dirs_deduplicate_repeated_roots(tmp_path: Path, monkeypatch):
    trt_libs = tmp_path / "tensorrt_libs"
    trt_libs.mkdir()
    monkeypatch.setattr(dll_paths.site, "getsitepackages", lambda: [str(tmp_path), str(tmp_path)])
    monkeypatch.setattr(dll_paths.site, "getusersitepackages", lambda: str(tmp_path))
    monkeypatch.setattr(dll_paths.sys, "path", [str(tmp_path)])

    assert _ORIGINAL_PYTHON_PACKAGE_DLL_DIRS() == [trt_libs]


def test_picks_up_cuda_path_when_present(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])
    cuda_root = tmp_path / "cuda"
    cuda_bin = cuda_root / "bin"
    cuda_bin.mkdir(parents=True)
    monkeypatch.setenv("CUDA_PATH", str(cuda_root))

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()

    assert [Path(p) for p in captured] == [cuda_bin.resolve()]


def test_extra_paths_are_registered_after_settings(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths(extra=[extra_dir])

    assert [Path(p) for p in captured] == [extra_dir.resolve()]


def test_registers_opencv_bin_dir_from_env(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    opencv_bin = tmp_path / "opencv" / "bin"
    opencv_bin.mkdir(parents=True)
    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setenv("VP_OPENCV_BIN_DIR", str(opencv_bin))
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()

    assert [Path(p) for p in captured] == [opencv_bin.resolve()]


def test_registers_opencv_root_bin_candidates_from_env(tmp_path: Path, monkeypatch):
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    root = tmp_path / "opencv"
    direct_bin = root / "bin"
    vc_bin = root / "build" / "x64" / "vc17" / "bin"
    direct_bin.mkdir(parents=True)
    vc_bin.mkdir(parents=True)
    monkeypatch.delenv("VP_TENSORRT_DIR", raising=False)
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setenv("VP_OPENCV_DIR", str(root))
    monkeypatch.setattr(dll_paths, "_scan_common_tensorrt_roots", lambda: [])

    captured: list[str] = []
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", captured.append)

    dll_paths.register_native_dll_paths()

    assert [Path(p) for p in captured] == [direct_bin.resolve(), vc_bin.resolve()]


def test_registers_directory_into_path_for_legacy_loader(tmp_path: Path, monkeypatch):
    """ONNX Runtime's TRT provider DLL resolves nvinfer_10.dll via the legacy
    LoadLibrary search order, which only honours PATH (not AddDllDirectory).
    register_native_dll_paths must therefore prepend the directory to PATH so
    transitive DLL imports resolve."""
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-only behaviour")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.delenv("CUDA_PATH", raising=False)
    monkeypatch.setenv("PATH", "C:\\some\\dir;C:\\other")
    monkeypatch.setattr(dll_paths.os, "add_dll_directory", lambda _path: None)

    dll_paths.register_native_dll_paths(tensorrt_dir=str(tmp_path))

    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0].lower() == str(bin_dir.resolve()).lower(), (
        f"expected bin dir to be the first PATH entry, got {parts!r}"
    )
