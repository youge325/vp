"""Video probing and capability discovery as pure functions."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
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

RATE_CONTROL_PROBE_ORDER = ("crf", "cq", "qp")
RATE_CONTROL_LABELS = {
    "crf": "CRF",
    "cq": "CQ",
    "qp": "QP",
    "bitrate": "Bitrate",
}
RATE_CONTROL_DEFAULTS = {
    "crf": 18,
    "cq": 23,
    "qp": 23,
    "bitrate": 8,
}
RATE_CONTROL_UNITS = {
    "crf": "CRF",
    "cq": "CQ",
    "qp": "QP",
    "bitrate": "Mbps",
}
RATE_CONTROL_PROBE_SOURCE = "color=size=256x256:rate=1"
DECODER_HARDWARE_PROBE_SOURCE = "testsrc2=size=256x256:rate=1"
DECODER_HARDWARE_SAMPLE_ENCODERS = {
    "h264": ("libx264", "h264_nvenc", "h264_qsv"),
    "hevc": ("libx265", "hevc_nvenc", "hevc_qsv"),
    "av1": ("libaom-av1", "libsvtav1", "av1_nvenc", "av1_qsv"),
}
DECODER_HARDWARE_DEVICE_PROBE_VALUES = tuple(str(index) for index in range(8))


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


def _find_option(options: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((option for option in options if option.get("name") == name), None)


def _rate_control_default(mode: str, option: dict[str, Any] | None) -> Any:
    default = option.get("defaultValue") if option else None
    if default is not None and not (isinstance(default, str) and not default.strip()):
        if isinstance(default, (int, float)) and not isinstance(default, bool) and default <= 0:
            return RATE_CONTROL_DEFAULTS[mode]
        return default
    return RATE_CONTROL_DEFAULTS[mode]


def _rate_control_probe_args(mode: str, value: Any) -> list[str]:
    if mode == "bitrate":
        return ["-b:v", "8M"]
    return [f"-{mode}", str(value)]


def _pixel_format_probe_args(options: list[dict[str, Any]]) -> list[str]:
    pix_fmt = _find_option(options, "pix_fmt")
    if not pix_fmt:
        return []
    value = pix_fmt.get("defaultValue")
    if value is None or (isinstance(value, str) and not value.strip()):
        choices = pix_fmt.get("choices") if isinstance(pix_fmt.get("choices"), list) else []
        value = choices[0].get("value") if choices and isinstance(choices[0], dict) else None
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    return ["-pix_fmt", str(value)]


def _rate_control_candidates(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for mode in RATE_CONTROL_PROBE_ORDER:
        option = _find_option(options, mode)
        if option is None:
            continue
        candidates.append(
            {
                "mode": mode,
                "label": RATE_CONTROL_LABELS[mode],
                "defaultValue": _rate_control_default(mode, option),
                "unit": RATE_CONTROL_UNITS[mode],
            }
        )

    candidates.append(
        {
            "mode": "bitrate",
            "label": RATE_CONTROL_LABELS["bitrate"],
            "defaultValue": RATE_CONTROL_DEFAULTS["bitrate"],
            "unit": RATE_CONTROL_UNITS["bitrate"],
        }
    )
    return candidates


def _verify_rate_control_mode(
    ffmpeg_path: str,
    codec: str,
    options: list[dict[str, Any]],
    mode: dict[str, Any],
) -> bool:
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        RATE_CONTROL_PROBE_SOURCE,
        "-frames:v",
        "1",
        "-an",
        "-c:v",
        codec,
    ]
    cmd.extend(_rate_control_probe_args(str(mode["mode"]), mode["defaultValue"]))
    cmd.extend(_pixel_format_probe_args(options))
    cmd.extend(["-f", "null", "-"])
    try:
        run_ffmpeg_command(cmd, timeout=30)
    except Exception as exc:  # pragma: no cover - exact FFmpeg errors vary by build
        logger.debug(
            "Rate control probe failed for encoder %s mode %s: %s",
            codec,
            mode["mode"],
            exc,
        )
        return False
    return True


def probe_rate_control_modes(
    ffmpeg_path: str,
    codec: str,
    options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    modes = [
        mode
        for mode in _rate_control_candidates(options)
        if _verify_rate_control_mode(ffmpeg_path, codec, options, mode)
    ]
    if not modes:
        logger.debug("No rate control modes passed FFmpeg verification for encoder %s", codec)
    return modes


def _unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _decoder_hardware_candidates(hardware_devices: list[str], hwaccels: list[str]) -> list[str]:
    available = set(hwaccels)
    return [device for device in _unique_in_order(hardware_devices) if device in available]


def _decoder_sample_encoder_candidates(codec: str, encoder_names: set[str]) -> list[str]:
    return [encoder for encoder in DECODER_HARDWARE_SAMPLE_ENCODERS.get(codec, ()) if encoder in encoder_names]


def _decoder_probe_sample_path(probe_dir: str, codec: str) -> str:
    return str(Path(probe_dir) / f"vp_decoder_probe_{codec}.mkv")


def _ensure_decoder_probe_sample(
    ffmpeg_path: str,
    codec: str,
    encoder_names: set[str],
    probe_dir: str,
    sample_cache: dict[str, str | None],
) -> str | None:
    cache_key = codec.lower()
    if cache_key in sample_cache:
        return sample_cache[cache_key]

    encoders = _decoder_sample_encoder_candidates(cache_key, encoder_names)
    if not encoders:
        logger.debug("No FFmpeg encoder is available to generate decoder probe sample for codec %s", codec)
        sample_cache[cache_key] = None
        return None

    sample_path = _decoder_probe_sample_path(probe_dir, cache_key)
    for encoder in encoders:
        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            DECODER_HARDWARE_PROBE_SOURCE,
            "-frames:v",
            "1",
            "-an",
            "-c:v",
            encoder,
            "-pix_fmt",
            "yuv420p",
            sample_path,
        ]
        try:
            run_ffmpeg_command(cmd, timeout=30)
            sample_cache[cache_key] = sample_path
            return sample_path
        except Exception as exc:  # pragma: no cover - exact FFmpeg errors vary by build
            logger.debug(
                "Failed to generate decoder probe sample for codec %s with encoder %s: %s",
                codec,
                encoder,
                exc,
            )

    sample_cache[cache_key] = None
    return None


def _verify_decoder_hardware_device(
    ffmpeg_path: str,
    decoder: str,
    device: str,
    sample_path: str,
) -> bool:
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-hwaccel",
        device,
        "-c:v",
        decoder,
        "-i",
        sample_path,
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]
    try:
        run_ffmpeg_command(cmd, timeout=30)
    except Exception as exc:  # pragma: no cover - exact FFmpeg errors vary by build
        logger.debug(
            "Decoder hardware probe failed for decoder %s device %s: %s",
            decoder,
            device,
            exc,
        )
        return False
    return True


def _verify_decoder_hardware_device_option(
    ffmpeg_path: str,
    decoder: str,
    device: str,
    device_value: str,
    sample_path: str,
) -> bool:
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-hwaccel",
        device,
        "-hwaccel_device",
        device_value,
        "-c:v",
        decoder,
        "-i",
        sample_path,
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]
    try:
        run_ffmpeg_command(cmd, timeout=30)
    except Exception as exc:  # pragma: no cover - exact FFmpeg errors vary by build
        logger.debug(
            "Decoder hardware device option probe failed for decoder %s device %s value %s: %s",
            decoder,
            device,
            device_value,
            exc,
        )
        return False
    return True


def probe_decoder_hardware_devices(
    ffmpeg_path: str,
    decoder: str,
    codec: str,
    hardware_devices: list[str],
    hwaccels: list[str],
    encoder_names: set[str],
    probe_dir: str | None = None,
    sample_cache: dict[str, str | None] | None = None,
) -> list[str]:
    candidates = _decoder_hardware_candidates(hardware_devices, hwaccels)
    if not candidates:
        return []

    if probe_dir is None:
        with tempfile.TemporaryDirectory(prefix="vp-decoder-probe-") as temp_dir:
            return probe_decoder_hardware_devices(
                ffmpeg_path,
                decoder,
                codec,
                hardware_devices,
                hwaccels,
                encoder_names,
                probe_dir=temp_dir,
                sample_cache={},
            )

    cache = sample_cache if sample_cache is not None else {}
    sample_path = _ensure_decoder_probe_sample(ffmpeg_path, codec, encoder_names, probe_dir, cache)
    if sample_path is None:
        logger.debug("No decoder hardware devices passed FFmpeg verification for decoder %s", decoder)
        return []

    devices = [
        device for device in candidates if _verify_decoder_hardware_device(ffmpeg_path, decoder, device, sample_path)
    ]
    if not devices:
        logger.debug("No decoder hardware devices passed FFmpeg verification for decoder %s", decoder)
    return devices


def probe_decoder_hardware_device_options(
    ffmpeg_path: str,
    decoder: str,
    codec: str,
    devices: list[str],
    encoder_names: set[str],
    probe_dir: str | None = None,
    sample_cache: dict[str, str | None] | None = None,
) -> dict[str, list[dict[str, str]]]:
    if not devices:
        return {}

    if probe_dir is None:
        with tempfile.TemporaryDirectory(prefix="vp-decoder-probe-") as temp_dir:
            return probe_decoder_hardware_device_options(
                ffmpeg_path,
                decoder,
                codec,
                devices,
                encoder_names,
                probe_dir=temp_dir,
                sample_cache={},
            )

    cache = sample_cache if sample_cache is not None else {}
    sample_path = _ensure_decoder_probe_sample(ffmpeg_path, codec, encoder_names, probe_dir, cache)
    if sample_path is None:
        logger.debug("No decoder hardware device options passed FFmpeg verification for decoder %s", decoder)
        return {device: [] for device in devices}

    options_by_device: dict[str, list[dict[str, str]]] = {}
    for device in devices:
        options = [
            {"value": value, "label": value}
            for value in DECODER_HARDWARE_DEVICE_PROBE_VALUES
            if _verify_decoder_hardware_device_option(ffmpeg_path, decoder, device, value, sample_path)
        ]
        if not options:
            logger.debug(
                "No decoder hardware device options passed FFmpeg verification for decoder %s device %s",
                decoder,
                device,
            )
        options_by_device[device] = options
    return options_by_device


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
