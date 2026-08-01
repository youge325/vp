"""Shared fail-fast guards for CLI commands."""

from __future__ import annotations

from app.adapters.ffmpeg_media import FFmpegMediaAdapter
from app.config import settings
from app.errors import TaskErrorCode, raise_error
from app.ports.media import MediaRuntimePort
from app.utils.file_utils import validate_input_path
from app.utils.ffmpeg.media_probe import is_available


def ensure_ffmpeg_available() -> FFmpegMediaAdapter:
    if not is_available(settings.FFMPEG_PATH):
        raise_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": settings.FFMPEG_PATH,
                "ffprobe_path": settings.FFPROBE_PATH,
            },
        )
    return FFmpegMediaAdapter(settings.FFMPEG_PATH, settings.FFPROBE_PATH)


def ensure_input_and_ffmpeg(input_path: str) -> MediaRuntimePort:
    if not validate_input_path(input_path):
        raise_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )
    return ensure_ffmpeg_available()
