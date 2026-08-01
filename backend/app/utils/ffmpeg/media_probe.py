"""Media metadata and FFmpeg availability probes."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from app.utils.subprocess_utils import hidden_subprocess_kwargs

from ._run import run_ffmpeg_command


def probe_video_info(ffprobe_path: str, input_path: str) -> dict[str, Any]:
    """Read one raw metadata document; the adapter owns cache policy."""
    result = run_ffmpeg_command(
        [
            ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]
    )
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        info = {}
    return info


def get_fps(info: dict[str, Any]) -> float:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            frame_rate = str(stream.get("r_frame_rate", "30/1"))
            numerator, _, denominator = frame_rate.partition("/")
            try:
                numerator_value = int(numerator)
                denominator_value = int(denominator or "1")
            except ValueError:
                return 30.0
            if denominator_value == 0:
                return 30.0
            return round(numerator_value / denominator_value, 3)
    return 30.0


def _frame_count_from_metadata(info: dict[str, Any]) -> int:
    for stream in info.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        raw = stream.get("nb_frames")
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0


def probe_frame_count(
    ffprobe_path: str,
    input_path: str,
    info: dict[str, Any],
    duration: float,
    fps: float,
) -> int:
    """Resolve frame count once; the adapter owns fingerprinted caching."""
    frame_count = _frame_count_from_metadata(info)
    if frame_count <= 0:
        result = run_ffmpeg_command(
            [
                ffprobe_path,
                "-v",
                "quiet",
                "-count_frames",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=nb_read_frames",
                "-print_format",
                "json",
                input_path,
            ]
        )
        try:
            streams = json.loads(result.stdout).get("streams", [])
            if streams:
                frame_count = int(streams[0].get("nb_read_frames", 0))
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    if frame_count <= 0:
        frame_count = int(duration * fps) if duration > 0 else 0
    return frame_count


def get_duration(info: dict[str, Any]) -> float:
    return float(info.get("format", {}).get("duration", 0))


def has_audio(info: dict[str, Any]) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))


def get_primary_video_codec(info: dict[str, Any]) -> str:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return str(stream.get("codec_name") or "")
    return ""


def get_primary_video_dimensions(info: dict[str, Any]) -> tuple[int, int]:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream.get("width", 0)), int(stream.get("height", 0))
    return 0, 0


def is_available(ffmpeg_path: str) -> bool:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
