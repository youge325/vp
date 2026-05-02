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

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_registered: set[str] = set()


def _candidate_dirs() -> list[Path]:
    """Build the ordered list of directories to register, dedup'd downstream."""
    candidates: list[Path] = []

    tensorrt_dir = (settings.TENSORRT_DIR or "").strip()
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

    cuda_path = os.environ.get("CUDA_PATH", "").strip()
    if cuda_path:
        cuda_bin = Path(cuda_path) / "bin"
        if cuda_bin.is_dir():
            candidates.append(cuda_bin)

    return candidates


def register_native_dll_paths(extra: Iterable[Path] | None = None) -> list[Path]:
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

    add_dll_directory = getattr(os, "add_dll_directory", None)

    targets: list[Path] = []
    for path in (*_candidate_dirs(), *(extra or [])):
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
    _registered.clear()
