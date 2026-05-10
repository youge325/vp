"""Encoding, transcoding, and audio processing as pure functions."""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any, Callable

from app.utils.logger import get_logger
from app.utils.subprocess_utils import hidden_subprocess_kwargs

from ._progress import _format_bitrate
from .io import _FFmpegPipeBase

logger = get_logger(__name__)


def _run_command(cmd: list[str], *, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
    logger.debug("Running FFmpeg command: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **hidden_subprocess_kwargs(),
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"FFmpeg command failed ({result.returncode}): {message}")
    return result


def _build_option_args(options: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in options.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        args.append(f"-{key}")
        if isinstance(value, bool):
            args.append("1" if value else "0")
        else:
            args.append(str(value))
    return args


def _default_pix_fmt(codec: str) -> str | None:
    defaults = {
        "libx264": "yuv420p",
        "libx265": "yuv420p10le",
        "libaom-av1": "yuv420p10le",
        "libsvtav1": "yuv420p10le",
        "h264_nvenc": "yuv420p",
        "hevc_nvenc": "p010le",
        "av1_nvenc": "p010le",
        "h264_qsv": "nv12",
        "hevc_qsv": "p010le",
        "av1_qsv": "p010le",
    }
    return defaults.get(codec)


def build_decode_input_args(input_path: str, decode_config: dict[str, Any] | None = None) -> list[str]:
    decode_config = decode_config or {}
    mode = decode_config.get("mode", "software")
    args: list[str] = []

    if mode == "hardware":
        hwaccel = str(decode_config.get("hwaccel") or "").strip()
        if hwaccel:
            args.extend(["-hwaccel", hwaccel])
        hwaccel_device = str(decode_config.get("hwaccelDevice") or "").strip()
        if hwaccel_device:
            args.extend(["-hwaccel_device", hwaccel_device])

    decoder = str(decode_config.get("decoder") or "").strip()
    if decoder and decoder != "software":
        args.extend(["-c:v", decoder])

    args.extend(_build_option_args(decode_config.get("options", {})))
    args.extend(["-i", input_path])
    return args


def build_encode_video_args(encode_config: dict[str, Any] | None = None) -> list[str]:
    encode_config = encode_config or {}
    codec = str(encode_config.get("codec") or "libx264")
    options = dict(encode_config.get("options", {}))
    if "pix_fmt" not in options:
        default_pix_fmt = _default_pix_fmt(codec)
        if default_pix_fmt:
            options["pix_fmt"] = default_pix_fmt

    args = ["-c:v", codec]
    rate_control = dict(encode_config.get("rateControl", {}))
    mode = str(rate_control.get("mode") or "").strip()
    value = rate_control.get("value")

    if mode == "crf" and value is not None:
        args.extend(["-crf", str(value)])
    elif mode == "cq" and value is not None:
        args.extend(["-cq", str(value)])
    elif mode == "qp" and value is not None:
        args.extend(["-qp", str(value)])
    elif mode == "bitrate" and value is not None:
        args.extend(["-b:v", _format_bitrate(value)])

    args.extend(_build_option_args(options))
    return args


def build_encode_output_args(output_path: str, encode_config: dict[str, Any] | None = None) -> list[str]:
    args = build_encode_video_args(encode_config)
    args.extend([output_path, "-y"])
    return args


def extract_audio(ffmpeg_path: str, input_path: str, output_path: str) -> str | None:
    cmd = [ffmpeg_path, "-i", input_path, "-vn", "-acodec", "copy", output_path, "-y"]
    try:
        _run_command(cmd)
    except Exception as exc:  # pragma: no cover - defensive boundary
        logger.warning("Audio extraction failed: %s", exc)
        return None
    if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
        return output_path
    return None


def merge_audio(ffmpeg_path: str, video_path: str, audio_path: str, output_path: str) -> str:
    cmd = [
        ffmpeg_path,
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        output_path,
        "-y",
    ]
    _run_command(cmd)
    return output_path


def concat_videos(ffmpeg_path: str, segment_paths: list[str], output_path: str) -> str:
    if not segment_paths:
        raise ValueError("segment_paths must not be empty")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    list_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".concat.txt",
            dir=os.path.dirname(output_path) or ".",
            delete=False,
        ) as handle:
            list_file_path = handle.name
            for path in segment_paths:
                normalized = path.replace("\\", "/").replace("'", "'\\''")
                handle.write(f"file '{normalized}'\n")

        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file_path,
            "-c",
            "copy",
            output_path,
            "-y",
        ]
        _run_command(cmd)
        return output_path
    finally:
        if list_file_path and os.path.isfile(list_file_path):
            os.remove(list_file_path)


def transcode_video(
    ffmpeg_path: str,
    *,
    input_path: str,
    output_path: str,
    decode_input_args: list[str],
    encode_output_args: list[str],
    output_fps: float | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    keep_audio: bool = True,
) -> str:
    cmd = [ffmpeg_path, "-hide_banner", "-loglevel", "error"]
    if progress_callback is not None:
        cmd.extend(["-nostats", "-progress", "pipe:2"])
    cmd.extend(decode_input_args)
    cmd.extend(["-map", "0:v:0"])
    if keep_audio:
        cmd.extend(["-map", "0:a?", "-c:a", "aac"])
    else:
        cmd.append("-an")
    if output_fps is not None:
        cmd.extend(["-r", str(output_fps)])
    cmd.extend(encode_output_args)
    if progress_callback is None:
        _run_command(cmd)
        return output_path

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        **hidden_subprocess_kwargs(),
    )
    monitor = _FFmpegPipeBase(process, progress_callback=progress_callback)
    monitor._wait_for_process()
    return output_path


def convert_format(
    ffmpeg_path: str,
    input_path: str,
    output_path: str,
    codec: str = "libx264",
    crf: int = 18,
    preset: str = "medium",
    audio_codec: str = "aac",
) -> str:
    cmd = [
        ffmpeg_path,
        "-i",
        input_path,
        "-c:v",
        codec,
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-c:a",
        audio_codec,
        output_path,
        "-y",
    ]
    _run_command(cmd)
    return output_path
