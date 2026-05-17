"""``python -m app info`` handler."""

from __future__ import annotations

import argparse
import os

from app.errors import ProcessError, TaskErrorCode, raise_error
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper


def cmd_info(args: argparse.Namespace) -> None:
    input_path = args.input
    if not os.path.isfile(input_path):
        raise_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file does not exist: {input_path}",
            details={"input_path": input_path},
        )

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

    try:
        info = ffmpeg.get_video_info(input_path)
        fps = ffmpeg.get_fps(input_path)
        frames = ffmpeg.get_frame_count(input_path)
        duration = ffmpeg.get_duration(input_path)
        has_audio = ffmpeg.has_audio(input_path)
        video_codec = ffmpeg.get_primary_video_codec(input_path)

        width = 0
        height = 0
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                break

        ndjson.info(
            fps=fps,
            frames=frames,
            duration=duration,
            hasAudio=has_audio,
            width=width,
            height=height,
            videoCodec=video_codec,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details["input_path"] = input_path
        raise pe
