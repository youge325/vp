"""Production FFmpeg facade tests."""

import pytest

from app.config import settings
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.ffmpeg._progress import _parse_progress_snapshot


def test_init_uses_configured_paths() -> None:
    wrapper = FFmpegWrapper()

    assert wrapper.ffmpeg_path == settings.FFMPEG_PATH
    assert wrapper.ffprobe_path == settings.FFPROBE_PATH


def test_is_available_with_nonexistent_path() -> None:
    assert FFmpegWrapper(ffmpeg_path="/nonexistent/ffmpeg").is_available() is False


def test_get_video_info_nonexistent_file() -> None:
    with pytest.raises((RuntimeError, FileNotFoundError)):
        FFmpegWrapper().get_video_info("/nonexistent/file.mp4")


def test_parse_progress_snapshot_extracts_runtime_values() -> None:
    parsed = _parse_progress_snapshot(
        {
            "frame": "240",
            "fps": "59.9",
            "speed": "1.25x",
            "out_time_us": "4000000",
            "progress": "continue",
        }
    )

    assert parsed == {
        "frame": 240,
        "fps": 59.9,
        "speed": 1.25,
        "out_time_seconds": 4.0,
        "progress": "continue",
    }
