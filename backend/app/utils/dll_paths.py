"""Native DLL search-path registration for Windows GPU runtimes.

ONNX Runtime's CUDA / TensorRT execution providers load NVIDIA shared
libraries (``nvinfer_10.dll``, ``cublasLt64_*.dll`` …) via standard Windows
``LoadLibrary``. When those libraries live outside the system PATH (for
example, a self-contained TensorRT install at ``D:\\TensorRT-10.14.1.48``),
they cannot be found and the EP silently falls back to CPU. This module
extends the in-process DLL search path before any onnxruntime session is
created so that a single ``VP_TENSORRT_DIR`` environment variable suffices.

The helper is a no-op on non-Windows platforms and idempotent: calling it
many times only registers each directory once.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from app.utils.logger import get_logger

logger = get_logger(__name__)

_registered: set[str] = set()
# Module-level cache for auto-discovered TensorRT roots so repeated calls do
# not re-scan the filesystem and spam the log.
_scanned_tensorrt_roots: list[Path] | None = None


def _scan_common_tensorrt_roots() -> list[Path]:
    """Scan typical TensorRT installation roots when VP_TENSORRT_DIR is unset."""
    global _scanned_tensorrt_roots
    if _scanned_tensorrt_roots is not None:
        return _scanned_tensorrt_roots

    roots: list[Path] = []
    seen: set[str] = set()
    # Common drive letters and prefixes on Windows
    for drive in ["C:", "D:", "E:"]:
        for prefix in ["TensorRT", "tensorrt"]:
            drive_path = Path(f"{drive}\\")
            if not drive_path.exists():
                continue
            try:
                for entry in drive_path.iterdir():
                    if entry.is_dir() and entry.name.lower().startswith(prefix.lower()):
                        bin_dir = entry / "bin"
                        if bin_dir.is_dir():
                            key = str(bin_dir.resolve()).lower()
                            if key not in seen:
                                seen.add(key)
                                roots.append(bin_dir)
            except (OSError, PermissionError):
                continue
    # Also check NVIDIA default install location
    nvidia_path = Path("C:\\Program Files\\NVIDIA")
    if nvidia_path.is_dir():
        try:
            for entry in nvidia_path.iterdir():
                if entry.is_dir() and "tensorrt" in entry.name.lower():
                    bin_dir = entry / "bin"
                    if bin_dir.is_dir():
                        key = str(bin_dir.resolve()).lower()
                        if key not in seen:
                            seen.add(key)
                            roots.append(bin_dir)
        except (OSError, PermissionError):
            pass
    _scanned_tensorrt_roots = roots
    # 仅在首次扫描成功时记录日志，后续调用直接返回缓存避免刷屏。
    if roots:
        logger.info("Auto-discovered TensorRT bin directories: %s", roots)
    return roots


def _candidate_dirs(tensorrt_dir: str | None = None) -> list[Path]:
    """Build the ordered list of directories to register, dedup'd downstream."""
    candidates: list[Path] = []

    if tensorrt_dir is None:
        tensorrt_dir = os.environ.get("VP_TENSORRT_DIR", "").strip()
    if tensorrt_dir:
        root = Path(tensorrt_dir).expanduser()
        bin_dir = root / "bin"
        if bin_dir.is_dir():
            candidates.append(bin_dir)
        else:
            logger.warning(
                "VP_TENSORRT_DIR=%s does not contain a 'bin' subdirectory; ignoring.",
                tensorrt_dir,
            )
    else:
        # When VP_TENSORRT_DIR is unset, try common install locations.
        # _scan_common_tensorrt_roots() caches results and only logs on first scan.
        candidates.extend(_scan_common_tensorrt_roots())

    cuda_path = os.environ.get("CUDA_PATH", "").strip()
    if cuda_path:
        cuda_bin = Path(cuda_path) / "bin"
        if cuda_bin.is_dir():
            candidates.append(cuda_bin)

    candidates.extend(_opencv_candidate_dirs())

    return candidates


def _opencv_candidate_dirs() -> list[Path]:
    """Return explicit OpenCV DLL directories from environment settings."""
    candidates: list[Path] = []

    opencv_bin_dir = os.environ.get("VP_OPENCV_BIN_DIR", "").strip()
    if opencv_bin_dir:
        candidates.append(Path(opencv_bin_dir).expanduser())

    opencv_root = os.environ.get("VP_OPENCV_DIR", "").strip()
    if not opencv_root:
        return candidates

    root = Path(opencv_root).expanduser()
    root_candidates = [
        root / "bin",
        root / "build" / "bin",
    ]
    root_candidates.extend(sorted(root.glob("x64/vc*/bin")))
    root_candidates.extend(sorted(root.glob("build/x64/vc*/bin")))
    root_candidates.extend(sorted(root.glob("install/x64/vc*/bin")))
    candidates.extend(root_candidates)
    if not any(path.is_dir() for path in root_candidates):
        logger.warning(
            "VP_OPENCV_DIR=%s does not contain a known OpenCV bin directory; "
            "set VP_OPENCV_BIN_DIR to the exact directory if cv2 still fails to import.",
            opencv_root,
        )
    return candidates


def register_native_dll_paths(
    tensorrt_dir: str | None = None,
    extra: Iterable[Path] | None = None,
) -> list[Path]:
    """Add GPU-runtime directories to the Windows DLL search path.

    Returns the list of directories registered on this call (excluding ones
    already registered by a previous call). On non-Windows hosts the function
    short-circuits and returns an empty list.

    Implementation note: ``os.add_dll_directory`` alone is **not enough** on
    Windows because ONNX Runtime's TensorRT provider DLL has a static import
    on ``nvinfer_10.dll`` resolved via the legacy ``LoadLibrary`` search order,
    which honours ``%PATH%`` but not directories registered via the newer
    ``AddDllDirectory`` API unless the loader opts in. We therefore *also*
    prepend each directory to ``os.environ['PATH']`` so the OS loader can find
    transitive dependencies.
    """
    if not sys.platform.startswith("win"):
        return []

    candidates = list(_candidate_dirs(tensorrt_dir))
    if extra:
        candidates.extend(extra)

    # 快速路径：所有候选目录都已经被注册过，跳过扫描和日志
    if all(str(p.resolve(strict=False)).lower() in _registered for p in candidates):
        return []

    add_dll_directory = getattr(os, "add_dll_directory", None)

    targets: list[Path] = []
    for path in candidates:
        resolved = path.resolve(strict=False)
        key = str(resolved).lower()
        if key in _registered:
            continue
        if not resolved.is_dir():
            logger.warning("Skipping non-existent DLL directory %s", resolved)
            continue
        if add_dll_directory is not None:
            try:
                add_dll_directory(str(resolved))
            except OSError as exc:
                logger.warning("os.add_dll_directory(%s) failed: %s", resolved, exc)
        # Always prepend to PATH so legacy LoadLibrary search picks it up.
        _prepend_to_path(str(resolved))
        _registered.add(key)
        targets.append(resolved)
        logger.info("Registered native DLL directory %s", resolved)

    return targets


def _prepend_to_path(directory: str) -> None:
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if any(part.lower() == directory.lower() for part in parts):
        return
    os.environ["PATH"] = directory + (os.pathsep + current if current else "")


def reset_registry_for_tests() -> None:
    """Test-only helper to forget previously-registered directories."""
    global _scanned_tensorrt_roots
    _registered.clear()
    _scanned_tensorrt_roots = None
