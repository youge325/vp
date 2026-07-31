"""Shared CLI guard behavior tests."""

from __future__ import annotations

import argparse

import pytest

from app.cli.commands import _guards, info
from app.adapters import FFmpegMediaAdapter
from app.errors import ProcessError, TaskErrorCode


class _FakeFFmpeg:
    ffmpeg_path = "fake-ffmpeg"
    ffprobe_path = "fake-ffprobe"

    def __init__(self, *, available: bool = True) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


def test_ffmpeg_guard_returns_available_wrapper(monkeypatch) -> None:
    ffmpeg = _FakeFFmpeg()
    monkeypatch.setattr(_guards, "FFmpegWrapper", lambda: ffmpeg)

    assert _guards.ensure_ffmpeg_available() is ffmpeg


def test_ffmpeg_guard_reports_resolved_binary_paths(monkeypatch) -> None:
    monkeypatch.setattr(_guards, "FFmpegWrapper", lambda: _FakeFFmpeg(available=False))

    with pytest.raises(ProcessError) as exc_info:
        _guards.ensure_ffmpeg_available()

    assert exc_info.value.code == TaskErrorCode.MISSING_FFMPEG
    assert exc_info.value.details == {
        "ffmpeg_path": "fake-ffmpeg",
        "ffprobe_path": "fake-ffprobe",
    }


def test_process_guard_rejects_invalid_input_before_constructing_ffmpeg(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        _guards,
        "FFmpegWrapper",
        lambda: pytest.fail("FFmpeg must not be constructed for invalid input"),
    )

    with pytest.raises(ProcessError) as exc_info:
        _guards.ensure_input_and_ffmpeg(str(tmp_path / "missing.mp4"))

    assert exc_info.value.code == TaskErrorCode.INVALID_INPUT


def test_process_guard_wires_ffmpeg_through_the_media_adapter(monkeypatch) -> None:
    ffmpeg = _FakeFFmpeg()
    monkeypatch.setattr(_guards, "validate_input_path", lambda _path: True)
    monkeypatch.setattr(_guards, "ensure_ffmpeg_available", lambda: ffmpeg)

    media = _guards.ensure_input_and_ffmpeg("input.mp4")

    assert isinstance(media, FFmpegMediaAdapter)


def test_info_keeps_existence_only_input_policy(monkeypatch) -> None:
    payload: list[object] = []

    class _InfoFFmpeg(_FakeFFmpeg):
        def get_video_info(self, _input_path: str) -> dict[str, object]:
            return {"streams": [{"codec_type": "video", "width": 16, "height": 9}]}

        def get_fps(self, _input_path: str) -> float:
            return 24.0

        def get_primary_video_codec(self, _input_path: str) -> str:
            return "h264"

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
