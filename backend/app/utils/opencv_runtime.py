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


__all__ = ["import_cv2"]
