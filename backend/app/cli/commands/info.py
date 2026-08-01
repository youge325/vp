"""``python -m app info`` handler."""

from __future__ import annotations

import argparse
import os

from app.cli.commands._guards import ensure_ffmpeg_available
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError, raise_error
from app.generated.contracts import VideoInfo
from app.generated.protocol_constants import BackendEnvelopeType
from app.ports.media import VideoInspection, VideoInspectionPort
from app.protocol.emitter import ndjson


def cmd_info(args: argparse.Namespace) -> None:
    input_path = args.input
    if not os.path.isfile(input_path):
        raise_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file does not exist: {input_path}",
            details={"input_path": input_path},
        )

    inspection_port: VideoInspectionPort = ensure_ffmpeg_available()

    try:
        inspection: VideoInspection = inspection_port.inspect_video(input_path)

        ndjson.emit(
            BackendEnvelopeType.INFO,
            VideoInfo(
                fps=inspection.fps,
                width=inspection.width,
                height=inspection.height,
                videoCodec=inspection.video_codec,
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details["input_path"] = input_path
        raise pe
