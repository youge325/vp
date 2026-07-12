"""``python -m app info`` handler."""

from __future__ import annotations

import argparse
import os

from app.cli.commands._guards import ensure_ffmpeg_available
from app.errors import ProcessError, TaskErrorCode, raise_error
from app.protocol import ndjson
from app.utils.ffmpeg.media_probe import get_primary_video_dimensions


def cmd_info(args: argparse.Namespace) -> None:
    input_path = args.input
    if not os.path.isfile(input_path):
        raise_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file does not exist: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = ensure_ffmpeg_available()

    try:
        info = ffmpeg.get_video_info(input_path)
        fps = ffmpeg.get_fps(input_path)
        video_codec = ffmpeg.get_primary_video_codec(input_path)
        width, height = get_primary_video_dimensions(info)

        ndjson.info(
            fps=fps,
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
