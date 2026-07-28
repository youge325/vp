"""Shared fail-fast guards for CLI commands."""

from __future__ import annotations

from app.adapters import FFmpegMediaAdapter
from app.errors import TaskErrorCode, raise_error
from app.ports.media import MediaRuntimePort
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import validate_input_path


def ensure_ffmpeg_available() -> FFmpegWrapper:
    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        raise_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )
    return ffmpeg


def ensure_input_and_ffmpeg(input_path: str) -> MediaRuntimePort:
    if not validate_input_path(input_path):
        raise_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )
    return FFmpegMediaAdapter(ensure_ffmpeg_available())
