from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app import config
from app.config import _Settings


def _executable_name(name: str) -> str:
    return f"{name}.exe" if sys.platform.startswith("win") else name


def _touch_executable(parent: Path, name: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / _executable_name(name)
    path.touch()
    return path


def _build_settings(runtime_root: str | Path, *, app_root: Path) -> _Settings:
    return _Settings(
        _env_file=None,
        APP_ROOT=str(app_root),
        RUNTIME_ROOT=str(runtime_root),
        PYTHON_EXECUTABLE="",
        FFMPEG_PATH="",
        FFPROBE_PATH="",
        RIFE_MODEL_DIR="",
    )


def test_external_ffmpeg_paths_are_resolved_once_in_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lookups: list[str] = []
    monkeypatch.setattr(config.shutil, "which", lambda name: lookups.append(name) or f"resolved-{name}")

    resolved = _build_settings("", app_root=tmp_path)

    assert resolved.FFMPEG_PATH == "resolved-ffmpeg"
    assert resolved.FFPROBE_PATH == "resolved-ffprobe"
    assert lookups == ["ffmpeg", "ffprobe"]


@pytest.mark.parametrize(("tool_name", "setting_name"), [("ffmpeg", "FFMPEG_PATH"), ("ffprobe", "FFPROBE_PATH")])
def test_runtime_tool_candidates_keep_shared_bin_precedence(
    tmp_path: Path,
    tool_name: str,
    setting_name: str,
) -> None:
    runtime_root = tmp_path / "runtime"
    candidates = [
        _touch_executable(runtime_root, tool_name),
        _touch_executable(runtime_root / "bin", tool_name),
        _touch_executable(runtime_root / tool_name, tool_name),
        _touch_executable(runtime_root / tool_name / "bin", tool_name),
    ]

    for expected in candidates:
        configured = _build_settings(runtime_root, app_root=tmp_path / "app")
        assert Path(getattr(configured, setting_name)) == expected
        expected.unlink()


def test_runtime_python_candidates_prefer_embedded_python_before_shared_bin(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    candidates = [
        _touch_executable(runtime_root, "python"),
        _touch_executable(runtime_root / "python", "python"),
        _touch_executable(runtime_root / "python" / "bin", "python"),
        _touch_executable(runtime_root / "bin", "python"),
    ]

    for expected in candidates:
        configured = _build_settings(runtime_root, app_root=tmp_path / "app")
        assert Path(configured.PYTHON_EXECUTABLE) == expected
        expected.unlink()


def test_runtime_mode_uses_the_configured_root_directly(tmp_path: Path) -> None:
    external = _build_settings("", app_root=tmp_path / "external-app")
    assert external.runtime_mode == "external"

    missing_root = tmp_path / "missing-runtime"
    expected_bundled = _build_settings(missing_root, app_root=tmp_path / "expected-app")
    assert expected_bundled.runtime_mode == "expected-bundled"

    bundled_root = tmp_path / "bundled-runtime"
    bundled_root.mkdir()
    bundled = _build_settings(bundled_root, app_root=tmp_path / "bundled-app")
    assert bundled.runtime_mode == "bundled"
