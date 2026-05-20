"""Video probing and capability discovery as pure functions."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from app.utils.logger import get_logger
from app.utils.subprocess_utils import hidden_subprocess_kwargs

from ._constants import (
    CODEC_LIST_RE,
    OPTION_LINE_RE,
    CHOICE_LINE_RE,
)
from ._progress import _coerce_default_value, _coerce_number
from ._run import run_ffmpeg_command

logger = get_logger(__name__)


def _probe_cache_key(input_path: str) -> tuple[str, int, int] | None:
    """Build the cache key for ``video_info_cache`` lookups.

    Phase C.1.4 — key now includes ``size`` alongside ``mtime_ns``. Some
    build tools preserve mtime when extracting or copying files, so a
    pure ``(path, mtime)`` key would happily hand back stale info for a
    completely different file. Adding ``size`` is essentially free here
    (``os.stat`` already returns it) and closes the collision window.
    """
    try:
        stat = os.stat(input_path)
    except OSError:
        return None
    return (os.path.abspath(input_path), stat.st_mtime_ns, stat.st_size)


def get_video_info(
    ffprobe_path: str,
    input_path: str,
    video_info_cache: dict[tuple[str, int, int], dict[str, Any]],
) -> dict[str, Any]:
    cache_key = _probe_cache_key(input_path)
    if cache_key is not None and cache_key in video_info_cache:
        return video_info_cache[cache_key]

    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        input_path,
    ]
    result = run_ffmpeg_command(cmd)
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        info = {}
    if cache_key is not None:
        video_info_cache[cache_key] = info
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
    """从容器/流元数据中解析帧数（不进行解码扫描）。

    ffprobe 默认输出的 stream.nb_frames 由容器写入；TS/MP4 等格式通常都有，
    损坏或恶意写入的文件会导致 0/缺失。返回 0 表示元数据不可信。
    """
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


def get_frame_count(
    ffprobe_path: str,
    input_path: str,
    info: dict[str, Any],
    duration: float,
    fps: float,
    frame_count_cache: dict[tuple[str, int, int], int],
) -> int:
    cache_key = _probe_cache_key(input_path)
    if cache_key is not None and cache_key in frame_count_cache:
        return frame_count_cache[cache_key]

    # 优先使用容器/流元数据中的 nb_frames（O(1)），只有缺失/异常时才退化为
    # -count_frames 扫描。后者在 4K HEVC 等大视频上需要几分钟软解全片。
    frame_count = _frame_count_from_metadata(info)

    if frame_count <= 0:
        cmd = [
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
        result = run_ffmpeg_command(cmd)
        try:
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            if streams:
                frame_count = int(streams[0].get("nb_read_frames", 0))
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    if frame_count <= 0:
        frame_count = int(duration * fps) if duration > 0 else 0

    if cache_key is not None and frame_count > 0:
        frame_count_cache[cache_key] = frame_count
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


def list_codec_names(ffmpeg_path: str, mode: str) -> list[str]:
    if mode not in {"encoders", "decoders"}:
        raise ValueError(f"Unsupported codec list mode: {mode}")
    cmd = [ffmpeg_path, "-hide_banner", f"-{mode}"]
    result = run_ffmpeg_command(cmd, timeout=30)
    names: list[str] = []
    for line in result.stdout.splitlines():
        match = CODEC_LIST_RE.match(line)
        if match:
            names.append(match.group("name"))
    return names


def list_hwaccels(ffmpeg_path: str) -> list[str]:
    result = run_ffmpeg_command([ffmpeg_path, "-hide_banner", "-hwaccels"], timeout=30)
    hwaccels: list[str] = []
    started = False
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Hardware acceleration methods"):
            started = True
            continue
        if started:
            hwaccels.append(stripped)
    return hwaccels


def describe_codec(ffmpeg_path: str, mode: str, name: str) -> str:
    if mode not in {"encoder", "decoder"}:
        raise ValueError(f"Unsupported codec help mode: {mode}")
    result = run_ffmpeg_command([ffmpeg_path, "-hide_banner", "-h", f"{mode}={name}"], timeout=30)
    return result.stdout


def _parse_supported_values(text: str, prefix: str) -> list[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip().split()
    return []


def parse_avoptions(help_text: str) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in help_text.splitlines():
        match = OPTION_LINE_RE.match(line.rstrip())
        if match:
            raw_kind = match.group("kind").strip()
            option_type = "string"
            if raw_kind == "boolean":
                option_type = "boolean"
            elif raw_kind in {"int", "float", "double"}:
                option_type = "number"
            option = {
                "name": match.group("name"),
                "label": match.group("name").replace("_", " "),
                "type": option_type,
                "defaultValue": _coerce_default_value(option_type, match.group("default")),
                "choices": [],
                "min": _coerce_number(match.group("min")),
                "max": _coerce_number(match.group("max")),
            }
            options.append(option)
            current = option
            continue

        choice_match = CHOICE_LINE_RE.match(line.rstrip())
        if choice_match and current is not None:
            choice_value = choice_match.group("value")
            current["choices"].append({"label": choice_value, "value": choice_value})

    normalized: list[dict[str, Any]] = []
    for option in options:
        normalized_option = dict(option)
        if normalized_option["choices"]:
            normalized_option["type"] = "choice"
        normalized.append(normalized_option)
    return normalized


def parse_codec_profile(
    mode: str,
    metadata: dict[str, Any],
    help_text: str,
) -> dict[str, Any]:
    pixel_formats = _parse_supported_values(help_text, "Supported pixel formats:")
    hardware_devices = _parse_supported_values(help_text, "Supported hardware devices:")
    options = parse_avoptions(help_text)
    if pixel_formats:
        options.insert(
            0,
            {
                "name": "pix_fmt",
                "label": "Pixel Format",
                "type": "choice",
                "defaultValue": pixel_formats[0],
                "choices": [{"label": value, "value": value} for value in pixel_formats],
                "min": None,
                "max": None,
            },
        )
    return {
        "name": metadata["name"],
        "label": metadata["label"],
        "family": metadata["family"],
        "codec": metadata["codec"],
        "available": True,
        "pixelFormats": pixel_formats,
        "hardwareDevices": hardware_devices,
        "options": options,
    }


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


def get_version(ffmpeg_path: str) -> str | None:
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
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
