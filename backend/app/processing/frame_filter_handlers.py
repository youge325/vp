"""Declarative CPU and tensor handlers for frame-filter steps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any, Callable

import numpy as np

from app.catalog.filter_geometry import crop_slices, padding, scale_output_dimensions
from app.processing.anime_cleanup import apply_anime_cleanup
from app.utils.opencv_runtime import import_cv2

type _FilterParams = Mapping[str, Any]
type _NumpyFilterHandler = Callable[[np.ndarray, _FilterParams], np.ndarray]


@dataclass(frozen=True, slots=True)
class _FilterHandler:
    numpy: _NumpyFilterHandler


_INTERP_MAP: dict[str, int] = {}


def _ensure_cv2() -> None:
    if _INTERP_MAP:
        return
    try:
        cv2 = import_cv2()
        _INTERP_MAP.update(
            {
                "lanczos4": cv2.INTER_LANCZOS4,
                "cubic": cv2.INTER_CUBIC,
                "area": cv2.INTER_AREA,
                "linear": cv2.INTER_LINEAR,
            }
        )
    except RuntimeError as exc:
        raise RuntimeError("frame_filter_chain requires OpenCV (cv2).") from exc


def _parse_hex_color(color_str: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(color_str))
    if not match:
        raise ValueError("Filter color must be a six-digit hexadecimal RGB value.")
    hex_value = match.group(1)
    return (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
    )


def _apply_numpy_scale(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    _ensure_cv2()
    cv2 = import_cv2()
    interpolation = _INTERP_MAP[str(params["interpolation"])]
    width, height = scale_output_dimensions(
        params,
        input_width=frame.shape[1],
        input_height=frame.shape[0],
    )
    if width == frame.shape[1] and height == frame.shape[0]:
        return frame
    return cv2.resize(frame, (width, height), interpolation=interpolation)


def _apply_numpy_crop(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    frame_height, frame_width = frame.shape[:2]
    rows, columns = crop_slices(params, frame_width=frame_width, frame_height=frame_height)
    return frame[rows, columns]


def _apply_numpy_pad(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    top, bottom, left, right = padding(params)
    if top == bottom == left == right == 0:
        return frame
    return cv2.copyMakeBorder(
        frame,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=_parse_hex_color(str(params["color"])),
    )


def _apply_numpy_sharpen(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    amount = float(params["amount"])
    if amount <= 0:
        return frame
    blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=3)
    return cv2.addWeighted(frame, 1.0 + amount, blurred, -amount, 0)


def _apply_numpy_denoise(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    strength = float(params["strength"])
    color_strength = float(params["colorStrength"])
    if strength <= 0 and color_strength <= 0:
        return frame
    return cv2.fastNlMeansDenoisingColored(
        frame,
        None,
        h=strength,
        hColor=color_strength,
        templateWindowSize=7,
        searchWindowSize=21,
    )


def _apply_numpy_color(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    brightness = float(params["brightness"])
    contrast = float(params["contrast"])
    saturation = float(params["saturation"])
    if brightness != 0.0 or contrast != 1.0:
        frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness * 127.5)
    if saturation != 1.0:
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return frame


def _apply_numpy_anime_cleanup(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    return apply_anime_cleanup(
        frame,
        profile=str(params["profile"]),
        denoise=float(params["denoise"]),
        edge_boost=float(params["edgeBoost"]),
    )


_FILTER_HANDLERS: Mapping[str, _FilterHandler] = MappingProxyType(
    {
        "scale": _FilterHandler(_apply_numpy_scale),
        "crop": _FilterHandler(_apply_numpy_crop),
        "pad": _FilterHandler(_apply_numpy_pad),
        "sharpen": _FilterHandler(_apply_numpy_sharpen),
        "denoise": _FilterHandler(_apply_numpy_denoise),
        "color": _FilterHandler(_apply_numpy_color),
        "anime_cleanup": _FilterHandler(_apply_numpy_anime_cleanup),
    }
)


def is_supported_filter_kind(kind: str) -> bool:
    return kind in _FILTER_HANDLERS


def apply_numpy_filter(kind: str, frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    handler = _FILTER_HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"Unsupported filter kind: {kind}")
    return handler.numpy(frame, params)


__all__ = [
    "apply_numpy_filter",
    "is_supported_filter_kind",
]
