"""Tests for OpenCV runtime import helpers."""

from __future__ import annotations

import builtins

import pytest

from app.utils import opencv_runtime


def test_import_cv2_error_mentions_opencv_env_paths(monkeypatch):
    monkeypatch.setattr(opencv_runtime, "register_native_dll_paths", lambda: None)
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("missing opencv dll")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError) as exc_info:
        opencv_runtime.import_cv2()

    message = str(exc_info.value)
    assert "VP_OPENCV_BIN_DIR" in message
    assert "VP_OPENCV_DIR" in message
