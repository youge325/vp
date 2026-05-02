"""App package root — registers TensorRT DLL paths at import time so that
onnxruntime (loaded lazily by sub-modules) can find nvinfer_10.dll."""

from __future__ import annotations

# Defer the import so that sub-modules that monkeypatch settings can do so
# before register_native_dll_paths reads settings.TENSORRT_DIR.
from app.utils.dll_paths import register_native_dll_paths

register_native_dll_paths()
