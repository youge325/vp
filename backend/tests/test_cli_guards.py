"""Shared CLI guard behavior tests."""

from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from app.cli.commands import _guards, info
from app.adapters.ffmpeg_media import FFmpegMediaAdapter
from app.errors import ProcessError, TaskErrorCode
from app.ports.media import VideoInspection


def test_ffmpeg_guard_returns_direct_media_adapter(monkeypatch) -> None:
    monkeypatch.setattr(_guards, "is_available", lambda path: path == "fake-ffmpeg")
    monkeypatch.setattr(
        _guards,
        "settings",
        SimpleNamespace(FFMPEG_PATH="fake-ffmpeg", FFPROBE_PATH="fake-ffprobe"),
    )

    assert isinstance(_guards.ensure_ffmpeg_available(), FFmpegMediaAdapter)


def test_ffmpeg_guard_reports_resolved_binary_paths(monkeypatch) -> None:
    monkeypatch.setattr(_guards, "is_available", lambda _path: False)
    monkeypatch.setattr(
        _guards,
        "settings",
        SimpleNamespace(FFMPEG_PATH="fake-ffmpeg", FFPROBE_PATH="fake-ffprobe"),
    )

    with pytest.raises(ProcessError) as exc_info:
        _guards.ensure_ffmpeg_available()

    assert exc_info.value.code == TaskErrorCode.MISSING_FFMPEG
    assert exc_info.value.details == {
        "ffmpeg_path": "fake-ffmpeg",
        "ffprobe_path": "fake-ffprobe",
    }


def test_process_guard_rejects_invalid_input_before_constructing_ffmpeg(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(_guards, "ensure_ffmpeg_available", lambda: pytest.fail("FFmpeg must not be constructed"))

    with pytest.raises(ProcessError) as exc_info:
        _guards.ensure_input_and_ffmpeg(str(tmp_path / "missing.mp4"))

    assert exc_info.value.code == TaskErrorCode.INVALID_INPUT


def test_process_guard_wires_ffmpeg_through_the_media_adapter(monkeypatch) -> None:
    ffmpeg = FFmpegMediaAdapter("fake-ffmpeg", "fake-ffprobe")
    monkeypatch.setattr(_guards, "validate_input_path", lambda _path: True)
    monkeypatch.setattr(_guards, "ensure_ffmpeg_available", lambda: ffmpeg)

    media = _guards.ensure_input_and_ffmpeg("input.mp4")

    assert isinstance(media, FFmpegMediaAdapter)


def test_info_keeps_existence_only_input_policy(monkeypatch) -> None:
    payload: list[object] = []

    class _InfoFFmpeg:
        def inspect_video(self, _input_path: str) -> VideoInspection:
            return VideoInspection(fps=24.0, width=16, height=9, video_codec="h264")

    monkeypatch.setattr(info.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(info, "ensure_ffmpeg_available", lambda: _InfoFFmpeg())
    monkeypatch.setattr(info.ndjson, "emit", lambda event_type, model: payload.append((event_type, model)))

    info.cmd_info(argparse.Namespace(input="input.unsupported-extension"))

    assert len(payload) == 1
    event_type, model = payload[0]
    assert event_type.value == "info"
    assert model.model_dump(by_alias=True, mode="json") == {
        "fps": 24.0,
        "width": 16,
        "height": 9,
        "videoCodec": "h264",
    }
