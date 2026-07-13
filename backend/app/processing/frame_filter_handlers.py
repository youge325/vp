"""Declarative CPU and tensor handlers for frame-filter steps."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any, Callable

import numpy as np

from app.processing.anime_cleanup import apply_anime_cleanup
from app.utils.opencv_runtime import import_cv2

type _FilterParams = dict[str, Any]
type _NumpyFilterHandler = Callable[[np.ndarray, _FilterParams], np.ndarray]
type _TensorFilterHandler = Callable[[Any, _FilterParams], Any]
type _TensorCapability = Callable[[_FilterParams], bool]


@dataclass(frozen=True, slots=True)
class _FilterHandler:
    numpy: _NumpyFilterHandler
    tensor: _TensorFilterHandler | None = None
    tensor_capability: _TensorCapability | None = None

    def can_apply_tensor(self, params: _FilterParams) -> bool:
        return self.tensor is not None and (self.tensor_capability is None or self.tensor_capability(params))


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
        return (0, 0, 0)
    hex_value = match.group(1)
    return (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
    )


def _apply_numpy_scale(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    _ensure_cv2()
    cv2 = import_cv2()
    mode = params.get("mode", "factor")
    interpolation = _INTERP_MAP.get(params.get("interpolation", "lanczos4"), cv2.INTER_LANCZOS4)
    if mode == "factor":
        factor = float(params.get("factor", 1.0))
        if factor == 1.0:
            return frame
        return cv2.resize(frame, None, fx=factor, fy=factor, interpolation=interpolation)

    width = int(params.get("width", frame.shape[1]))
    height = int(params.get("height", frame.shape[0]))
    if width == frame.shape[1] and height == frame.shape[0]:
        return frame
    return cv2.resize(frame, (width, height), interpolation=interpolation)


def _apply_numpy_crop(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    x = max(0, int(params.get("x", 0)))
    y = max(0, int(params.get("y", 0)))
    width = int(params.get("width", frame.shape[1]))
    height = int(params.get("height", frame.shape[0]))
    frame_height, frame_width = frame.shape[:2]
    return frame[y : min(frame_height, y + height), x : min(frame_width, x + width)]


def _apply_numpy_pad(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    top = int(params.get("top", 0))
    bottom = int(params.get("bottom", 0))
    left = int(params.get("left", 0))
    right = int(params.get("right", 0))
    if top == bottom == left == right == 0:
        return frame
    return cv2.copyMakeBorder(
        frame,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=_parse_hex_color(params.get("color", "#000000")),
    )


def _apply_numpy_sharpen(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    amount = float(params.get("amount", 0.5))
    if amount <= 0:
        return frame
    blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=3)
    return cv2.addWeighted(frame, 1.0 + amount, blurred, -amount, 0)


def _apply_numpy_denoise(frame: np.ndarray, params: _FilterParams) -> np.ndarray:
    cv2 = import_cv2()
    strength = float(params.get("strength", 10))
    color_strength = float(params.get("colorStrength", 10))
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
    brightness = float(params.get("brightness", 0.0))
    contrast = float(params.get("contrast", 1.0))
    saturation = float(params.get("saturation", 1.0))
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
        profile=str(params.get("profile", "clean-lines")),
        denoise=params.get("denoise"),
        edge_boost=params.get("edgeBoost"),
    )


def _apply_tensor_scale(tensor: Any, params: _FilterParams) -> Any:
    import torch.nn.functional as functional

    mode = params.get("mode", "factor")
    height = int(tensor.shape[-2])
    width = int(tensor.shape[-1])
    if mode == "factor":
        factor = float(params.get("factor", 1.0))
        if factor == 1.0:
            return tensor
        target_size = (max(1, int(round(height * factor))), max(1, int(round(width * factor))))
    else:
        target_size = (int(params.get("height", height)), int(params.get("width", width)))
        if target_size == (height, width):
            return tensor

    torch_mode = {
        "area": "area",
        "linear": "bilinear",
        "cubic": "bicubic",
        "lanczos4": "bicubic",
    }.get(params.get("interpolation", "lanczos4"), "bicubic")
    if torch_mode == "area":
        return functional.interpolate(tensor, size=target_size, mode=torch_mode)
    return functional.interpolate(tensor, size=target_size, mode=torch_mode, align_corners=False).clamp(0.0, 1.0)


def _apply_tensor_crop(tensor: Any, params: _FilterParams) -> Any:
    x = max(0, int(params.get("x", 0)))
    y = max(0, int(params.get("y", 0)))
    width = int(params.get("width", tensor.shape[-1]))
    height = int(params.get("height", tensor.shape[-2]))
    frame_height = int(tensor.shape[-2])
    frame_width = int(tensor.shape[-1])
    return tensor[:, :, y : min(frame_height, y + height), x : min(frame_width, x + width)]


def _apply_tensor_pad(tensor: Any, params: _FilterParams) -> Any:
    import torch

    top = int(params.get("top", 0))
    bottom = int(params.get("bottom", 0))
    left = int(params.get("left", 0))
    right = int(params.get("right", 0))
    if top == bottom == left == right == 0:
        return tensor

    batch, channels, height, width = tensor.shape
    output = torch.empty(
        (batch, channels, height + top + bottom, width + left + right),
        dtype=tensor.dtype,
        device=tensor.device,
    )
    color = _parse_hex_color(params.get("color", "#000000"))
    fill = torch.tensor(color[:channels], dtype=tensor.dtype, device=tensor.device).view(1, channels, 1, 1) / 255.0
    output.copy_(fill.expand_as(output))
    output[:, :, top : top + height, left : left + width] = tensor
    return output


def _apply_tensor_sharpen(tensor: Any, params: _FilterParams) -> Any:
    import torch
    import torch.nn.functional as functional

    amount = float(params.get("amount", 0.5))
    if amount <= 0:
        return tensor

    sigma = 3.0
    radius = int(round(sigma * 3))
    coordinates = torch.arange(-radius, radius + 1, dtype=tensor.dtype, device=tensor.device)
    kernel_1d = torch.exp(-(coordinates**2) / (2 * sigma * sigma))
    kernel_1d = kernel_1d / kernel_1d.sum()
    channels = int(tensor.shape[1])
    kernel_h = kernel_1d.view(1, 1, 1, -1).expand(channels, 1, 1, -1)
    kernel_v = kernel_1d.view(1, 1, -1, 1).expand(channels, 1, -1, 1)
    blurred = functional.conv2d(
        functional.pad(tensor, (radius, radius, 0, 0), mode="replicate"),
        kernel_h,
        groups=channels,
    )
    blurred = functional.conv2d(
        functional.pad(blurred, (0, 0, radius, radius), mode="replicate"),
        kernel_v,
        groups=channels,
    )
    return (tensor * (1.0 + amount) - blurred * amount).clamp(0.0, 1.0)


def _apply_tensor_denoise(tensor: Any, params: _FilterParams) -> Any:
    strength = float(params.get("strength", 10))
    color_strength = float(params.get("colorStrength", 10))
    if strength <= 0 and color_strength <= 0:
        return tensor
    raise RuntimeError("frame_filter_chain denoise does not support tensor processing.")


def _can_apply_tensor_denoise(params: _FilterParams) -> bool:
    return float(params.get("strength", 10)) <= 0 and float(params.get("colorStrength", 10)) <= 0


def _apply_tensor_color(tensor: Any, params: _FilterParams) -> Any:
    import torch

    brightness = float(params.get("brightness", 0.0))
    contrast = float(params.get("contrast", 1.0))
    saturation = float(params.get("saturation", 1.0))
    if brightness != 0.0 or contrast != 1.0:
        tensor = (tensor * contrast + brightness * 0.5).clamp(0.0, 1.0)
    if saturation != 1.0:
        weights = torch.tensor([0.299, 0.587, 0.114], dtype=tensor.dtype, device=tensor.device).view(1, 3, 1, 1)
        gray = (tensor[:, :3] * weights).sum(dim=1, keepdim=True)
        rgb = (gray + (tensor[:, :3] - gray) * saturation).clamp(0.0, 1.0)
        tensor = rgb if tensor.shape[1] == 3 else torch.cat([rgb, tensor[:, 3:]], dim=1)
    return tensor.clamp(0.0, 1.0)


_FILTER_HANDLERS: Mapping[str, _FilterHandler] = MappingProxyType(
    {
        "scale": _FilterHandler(_apply_numpy_scale, _apply_tensor_scale),
        "crop": _FilterHandler(_apply_numpy_crop, _apply_tensor_crop),
        "pad": _FilterHandler(_apply_numpy_pad, _apply_tensor_pad),
        "sharpen": _FilterHandler(_apply_numpy_sharpen, _apply_tensor_sharpen),
        "denoise": _FilterHandler(
            _apply_numpy_denoise,
            _apply_tensor_denoise,
            _can_apply_tensor_denoise,
        ),
        "color": _FilterHandler(_apply_numpy_color, _apply_tensor_color),
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


def can_apply_tensor_filter(kind: str, params: _FilterParams) -> bool:
    handler = _FILTER_HANDLERS.get(kind)
    return handler is not None and handler.can_apply_tensor(params)


def apply_tensor_filter(kind: str, tensor: Any, params: _FilterParams) -> Any:
    handler = _FILTER_HANDLERS.get(kind)
    if handler is None or handler.tensor is None:
        raise ValueError(f"Unsupported filter kind: {kind}")
    return handler.tensor(tensor, params)


__all__ = [
    "apply_numpy_filter",
    "apply_tensor_filter",
    "can_apply_tensor_filter",
    "is_supported_filter_kind",
]
