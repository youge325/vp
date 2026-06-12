"""OpenCV import helpers with Windows GPU DLL path registration."""

from __future__ import annotations

from typing import Any

from app.utils.dll_paths import register_native_dll_paths


def import_cv2() -> Any:
    """Import ``cv2`` after registering native GPU DLL search paths."""
    register_native_dll_paths()
    try:
        import cv2
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "OpenCV (cv2) could not be imported. If you use a custom GPU OpenCV "
            "build on Windows, set VP_OPENCV_BIN_DIR to its DLL bin directory "
            "or VP_OPENCV_DIR to the OpenCV install/build root."
        ) from exc
    return cv2


def get_cuda_device_count() -> int:
    """Return OpenCV CUDA device count, or 0 when CUDA support is unavailable."""
    cv2 = import_cv2()
    cuda = getattr(cv2, "cuda", None)
    get_count = getattr(cuda, "getCudaEnabledDeviceCount", None)
    if not callable(get_count):
        return 0
    try:
        return max(int(get_count()), 0)
    except Exception:
        return 0


__all__ = ["get_cuda_device_count", "import_cv2"]
