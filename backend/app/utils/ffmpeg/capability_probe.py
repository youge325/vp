"""FFmpeg codec capability probing and parser functions."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.utils.logger import get_logger

from ._constants import (
    CODEC_LIST_RE,
    OPTION_LINE_RE,
    CHOICE_LINE_RE,
)
from ._progress import _coerce_default_value, _coerce_number
from ._run import run_ffmpeg_command

_logger = get_logger(__name__)

_RATE_CONTROL_PROBE_ORDER = ("crf", "cq", "qp")
_RATE_CONTROL_LABELS = {
    "crf": "CRF",
    "cq": "CQ",
    "qp": "QP",
    "bitrate": "Bitrate",
}
_RATE_CONTROL_DEFAULTS = {
    "crf": 18,
    "cq": 23,
    "qp": 23,
    "bitrate": 8,
}
_RATE_CONTROL_UNITS = {
    "crf": "CRF",
    "cq": "CQ",
    "qp": "QP",
    "bitrate": "Mbps",
}
_RATE_CONTROL_PROBE_SOURCE = "color=size=256x256:rate=1"
_DECODER_HARDWARE_PROBE_SOURCE = "testsrc2=size=256x256:rate=1"
_DECODER_HARDWARE_SAMPLE_ENCODERS = {
    "h264": ("libx264", "h264_nvenc", "h264_qsv"),
    "hevc": ("libx265", "hevc_nvenc", "hevc_qsv"),
    "av1": ("libaom-av1", "libsvtav1", "av1_nvenc", "av1_qsv"),
}
_DECODER_HARDWARE_DEVICE_PROBE_VALUES = tuple(str(index) for index in range(8))


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


def _parse_avoptions(help_text: str) -> list[dict[str, Any]]:
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
    metadata: dict[str, Any],
    help_text: str,
) -> dict[str, Any]:
    pixel_formats = _parse_supported_values(help_text, "Supported pixel formats:")
    hardware_devices = _parse_supported_values(help_text, "Supported hardware devices:")
    options = _parse_avoptions(help_text)
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
        "hardwareDevices": hardware_devices,
        "options": options,
    }


def _find_option(options: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((option for option in options if option.get("name") == name), None)


def _rate_control_default(mode: str, option: dict[str, Any] | None) -> Any:
    default = option.get("defaultValue") if option else None
    if default is not None and not (isinstance(default, str) and not default.strip()):
        if isinstance(default, (int, float)) and not isinstance(default, bool) and default <= 0:
            return _RATE_CONTROL_DEFAULTS[mode]
        return default
    return _RATE_CONTROL_DEFAULTS[mode]


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
    for mode in _RATE_CONTROL_PROBE_ORDER:
        option = _find_option(options, mode)
        if option is None:
            continue
        candidates.append(
            {
                "mode": mode,
                "label": _RATE_CONTROL_LABELS[mode],
                "defaultValue": _rate_control_default(mode, option),
                "unit": _RATE_CONTROL_UNITS[mode],
            }
        )

    candidates.append(
        {
            "mode": "bitrate",
            "label": _RATE_CONTROL_LABELS["bitrate"],
            "defaultValue": _RATE_CONTROL_DEFAULTS["bitrate"],
            "unit": _RATE_CONTROL_UNITS["bitrate"],
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
        _RATE_CONTROL_PROBE_SOURCE,
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
        _logger.debug(
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
        _logger.debug("No rate control modes passed FFmpeg verification for encoder %s", codec)
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
    return [encoder for encoder in _DECODER_HARDWARE_SAMPLE_ENCODERS.get(codec, ()) if encoder in encoder_names]


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
        _logger.debug("No FFmpeg encoder is available to generate decoder probe sample for codec %s", codec)
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
            _DECODER_HARDWARE_PROBE_SOURCE,
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
            _logger.debug(
                "Failed to generate decoder probe sample for codec %s with encoder %s: %s",
                codec,
                encoder,
                exc,
            )

    sample_cache[cache_key] = None
    return None


def _verify_decoder_hardware(
    ffmpeg_path: str,
    decoder: str,
    device: str,
    sample_path: str,
    *,
    device_value: str | None = None,
) -> bool:
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-hwaccel",
        device,
    ]
    if device_value is not None:
        cmd.extend(["-hwaccel_device", device_value])
    cmd.extend(
        [
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
    )
    try:
        run_ffmpeg_command(cmd, timeout=30)
    except Exception as exc:  # pragma: no cover - exact FFmpeg errors vary by build
        if device_value is None:
            _logger.debug(
                "Decoder hardware probe failed for decoder %s device %s: %s",
                decoder,
                device,
                exc,
            )
        else:
            _logger.debug(
                "Decoder hardware device option probe failed for decoder %s device %s value %s: %s",
                decoder,
                device,
                device_value,
                exc,
            )
        return False
    return True


@contextmanager
def _decoder_probe_workspace(
    probe_dir: str | None,
    sample_cache: dict[str, str | None] | None,
) -> Iterator[tuple[str, dict[str, str | None]]]:
    if probe_dir is not None:
        yield probe_dir, sample_cache if sample_cache is not None else {}
        return

    with tempfile.TemporaryDirectory(prefix="vp-decoder-probe-") as temp_dir:
        yield temp_dir, {}


def probe_decoder_hardware_capabilities(
    ffmpeg_path: str,
    decoder: str,
    codec: str,
    hardware_devices: list[str],
    hwaccels: list[str],
    encoder_names: set[str],
    probe_dir: str | None = None,
    sample_cache: dict[str, str | None] | None = None,
) -> tuple[list[str], dict[str, list[dict[str, str]]]]:
    candidates = _decoder_hardware_candidates(hardware_devices, hwaccels)
    if not candidates:
        return [], {}

    with _decoder_probe_workspace(probe_dir, sample_cache) as (resolved_probe_dir, cache):
        sample_path = _ensure_decoder_probe_sample(ffmpeg_path, codec, encoder_names, resolved_probe_dir, cache)
        if sample_path is None:
            _logger.debug("No decoder hardware devices passed FFmpeg verification for decoder %s", decoder)
            return [], {}

        devices = [
            device for device in candidates if _verify_decoder_hardware(ffmpeg_path, decoder, device, sample_path)
        ]
        if not devices:
            _logger.debug("No decoder hardware devices passed FFmpeg verification for decoder %s", decoder)

        options_by_device: dict[str, list[dict[str, str]]] = {}
        for device in devices:
            options = [
                {"value": value, "label": value}
                for value in _DECODER_HARDWARE_DEVICE_PROBE_VALUES
                if _verify_decoder_hardware(
                    ffmpeg_path,
                    decoder,
                    device,
                    sample_path,
                    device_value=value,
                )
            ]
            if not options:
                _logger.debug(
                    "No decoder hardware device options passed FFmpeg verification for decoder %s device %s",
                    decoder,
                    device,
                )
            options_by_device[device] = options
        return devices, options_by_device
