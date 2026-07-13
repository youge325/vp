"""FFmpeg progress parsing utilities."""

from __future__ import annotations

from typing import Any, Callable

EncodeProgressCallback = Callable[[int, float | None, float | None, float | None, str], None]


def make_encode_progress_callback(
    callback: EncodeProgressCallback | None,
    *,
    frame_offset: int = 0,
) -> Callable[[dict[str, Any]], None] | None:
    if callback is None:
        return None

    def report(progress: dict[str, Any]) -> None:
        callback(
            frame_offset + int(progress.get("frame") or 0),
            progress.get("fps"),
            progress.get("speed"),
            progress.get("out_time_seconds"),
            str(progress.get("progress") or ""),
        )

    return report


def _parse_progress_float(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    text = raw_value.strip()
    if not text or text.upper() == "N/A":
        return None
    if text.endswith("x"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def _parse_progress_int(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    text = raw_value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_progress_out_time_seconds(snapshot: dict[str, str]) -> float | None:
    for key in ("out_time_us", "out_time_ms"):
        value = _parse_progress_int(snapshot.get(key))
        if value is None:
            continue
        scale = 1_000_000 if key == "out_time_us" else 1_000
        return value / scale

    raw_value = snapshot.get("out_time")
    if not raw_value:
        return None

    try:
        hours, minutes, seconds = raw_value.strip().split(":")
        return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    except ValueError:
        return None


def _parse_progress_snapshot(snapshot: dict[str, str]) -> dict[str, Any]:
    return {
        "frame": _parse_progress_int(snapshot.get("frame")) or 0,
        "fps": _parse_progress_float(snapshot.get("fps")),
        "speed": _parse_progress_float(snapshot.get("speed")),
        "out_time_seconds": _parse_progress_out_time_seconds(snapshot),
        "progress": snapshot.get("progress", ""),
    }


def _coerce_number(value: str | None) -> int | float | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"int_max", "auto", "unknown", "-inf", "inf"}:
        return None
    try:
        if "." in lowered:
            return float(lowered)
        return int(lowered)
    except ValueError:
        return None


def _coerce_default_value(kind: str, raw: str | None) -> Any:
    if raw is None:
        return None
    text = raw.strip()
    if kind == "boolean":
        return text.lower() in {"1", "true", "yes", "on", "auto"}
    if kind == "number":
        return _coerce_number(text)
    return text


def _format_bitrate(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "8M"
    if text.lower().endswith(("k", "m", "g")):
        return text.upper()
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return f"{int(numeric)}M"
    return f"{numeric}M"
