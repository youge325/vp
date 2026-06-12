"""帧级图像滤镜链算法 —— 预处理 / 后处理通用实现。

通过 OpenCV 对 numpy HWC-RGB 帧进行逐帧处理，支持多步滤镜叠加。
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np

from app.algorithms.base import IAlgorithm
from app.algorithms.tensor_backend import ITensorBackend
from app.utils.logger import get_logger
from app.utils.opencv_runtime import import_cv2

logger = get_logger(__name__)

_INTERP_MAP: dict[str, int] = {}


def _ensure_cv2() -> None:
    """延迟加载 cv2，避免在服务端启动时强依赖。"""
    global _INTERP_MAP
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


class FrameFilterChainAlgorithm(IAlgorithm):
    """帧级滤镜链：对每帧顺序应用一组滤镜配置。"""

    def __init__(self, tensor_backend: ITensorBackend | None = None, **kwargs: Any):
        self._tensor_backend = tensor_backend
        self._filters: list[dict[str, Any]] = kwargs.get("filters") or []
        self._validate_filters()

    def _validate_filters(self) -> None:
        for step in self._filters:
            kind = step.get("kind")
            if kind not in {"scale", "crop", "pad", "sharpen", "denoise", "color"}:
                raise ValueError(f"Unknown filter kind: {kind}")
            if not isinstance(step.get("params"), dict):
                raise ValueError(f"Filter step '{kind}' missing params dict.")

    def process_frame(self, frame: Any, **kwargs: Any) -> Any:
        if self._tensor_backend is not None and self.can_process_tensor(self._tensor_backend):
            return self.process_tensor(frame, self._tensor_backend)
        if self._tensor_backend is None:
            return self.process_numpy(frame)
        np_frame = self._tensor_backend.tensor_to_numpy(frame)
        np_frame = self.process_numpy(np_frame)
        return self._tensor_backend.numpy_to_tensor(np_frame)

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        """Apply the OpenCV filter chain directly on a CPU numpy frame."""
        return self._apply_filters(frame)

    def can_process_tensor(self, backend: Any) -> bool:
        """Return whether this filter chain can run on a backend tensor."""
        if _backend_name(backend) != "pytorch":
            return False
        return all(self._tensor_filter_supported(step) for step in self._filters)

    def process_tensor(self, tensor: Any, backend: Any) -> Any:
        """Apply the filter chain directly on a PyTorch tensor."""
        if not self.can_process_tensor(backend):
            raise RuntimeError("frame_filter_chain does not support tensor processing for this filter set.")
        return self._apply_tensor_filters(tensor)

    def process_frame_batch(self, frames: list[Any], **kwargs: Any) -> list[Any]:
        return [self.process_frame(f) for f in frames]

    def get_name(self) -> str:
        return "帧级滤镜链"

    def validate(self) -> bool:
        try:
            _ensure_cv2()
            self._validate_filters()
            return True
        except Exception:
            return False

    def get_description(self) -> str:
        names = [s.get("kind", "?") for s in self._filters]
        return f"OpenCV 帧级滤镜链: {' → '.join(names) if names else '无滤镜'}"

    # ------------------------------------------------------------------
    # 滤镜实现
    # ------------------------------------------------------------------
    def _apply_filters(self, frame: np.ndarray) -> np.ndarray:
        _ensure_cv2()

        for step in self._filters:
            if not step.get("enabled", True):
                continue
            kind = step["kind"]
            params = step.get("params", {})
            handler = getattr(self, f"_apply_{kind}", None)
            if handler is None:
                raise ValueError(f"Unsupported filter kind: {kind}")
            frame = handler(frame, params)
        return frame

    def _apply_scale(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        cv2 = import_cv2()

        mode = params.get("mode", "factor")
        interp_name = params.get("interpolation", "lanczos4")
        interp = _INTERP_MAP.get(interp_name, cv2.INTER_LANCZOS4)

        if mode == "factor":
            factor = float(params.get("factor", 1.0))
            if factor == 1.0:
                return frame
            return cv2.resize(frame, None, fx=factor, fy=factor, interpolation=interp)

        # mode == "resolution"
        width = int(params.get("width", frame.shape[1]))
        height = int(params.get("height", frame.shape[0]))
        if width == frame.shape[1] and height == frame.shape[0]:
            return frame
        return cv2.resize(frame, (width, height), interpolation=interp)

    def _apply_crop(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        x = max(0, int(params.get("x", 0)))
        y = max(0, int(params.get("y", 0)))
        width = int(params.get("width", frame.shape[1]))
        height = int(params.get("height", frame.shape[0]))
        h, w = frame.shape[:2]
        x2 = min(w, x + width)
        y2 = min(h, y + height)
        return frame[y:y2, x:x2]

    @staticmethod
    def _parse_hex_color(color_str: str) -> tuple[int, int, int]:
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(color_str))
        if not m:
            return (0, 0, 0)
        hex_val = m.group(1)
        return (
            int(hex_val[0:2], 16),
            int(hex_val[2:4], 16),
            int(hex_val[4:6], 16),
        )

    def _apply_pad(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        cv2 = import_cv2()

        top = int(params.get("top", 0))
        bottom = int(params.get("bottom", 0))
        left = int(params.get("left", 0))
        right = int(params.get("right", 0))
        if top == bottom == left == right == 0:
            return frame
        color_rgb = self._parse_hex_color(params.get("color", "#000000"))
        return cv2.copyMakeBorder(frame, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color_rgb)

    def _apply_sharpen(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        cv2 = import_cv2()

        amount = float(params.get("amount", 0.5))
        if amount <= 0:
            return frame
        blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=3)
        return cv2.addWeighted(frame, 1.0 + amount, blurred, -amount, 0)

    def _apply_denoise(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
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

    def _apply_color(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        cv2 = import_cv2()

        brightness = float(params.get("brightness", 0.0))
        contrast = float(params.get("contrast", 1.0))
        saturation = float(params.get("saturation", 1.0))

        # brightness + contrast
        if brightness != 0.0 or contrast != 1.0:
            beta = brightness * 127.5
            frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=beta)

        # saturation
        if saturation != 1.0:
            hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
            hsv[:, :, 1] *= saturation
            hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
            frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

        return frame

    # ------------------------------------------------------------------
    # Tensor filter implementation (PyTorch NCHW float [0,1])
    # ------------------------------------------------------------------
    def _tensor_filter_supported(self, step: dict[str, Any]) -> bool:
        if not step.get("enabled", True):
            return True
        kind = step.get("kind")
        if kind in {"scale", "crop", "pad", "sharpen", "color"}:
            return True
        if kind == "denoise":
            params = step.get("params", {})
            return float(params.get("strength", 10)) <= 0 and float(params.get("colorStrength", 10)) <= 0
        return False

    def _apply_tensor_filters(self, tensor: Any) -> Any:
        for step in self._filters:
            if not step.get("enabled", True):
                continue
            kind = step["kind"]
            params = step.get("params", {})
            if kind == "scale":
                tensor = self._apply_tensor_scale(tensor, params)
            elif kind == "crop":
                tensor = self._apply_tensor_crop(tensor, params)
            elif kind == "pad":
                tensor = self._apply_tensor_pad(tensor, params)
            elif kind == "sharpen":
                tensor = self._apply_tensor_sharpen(tensor, params)
            elif kind == "color":
                tensor = self._apply_tensor_color(tensor, params)
            elif kind == "denoise":
                tensor = self._apply_tensor_denoise(tensor, params)
            else:
                raise ValueError(f"Unsupported filter kind: {kind}")
        return tensor

    def _apply_tensor_scale(self, tensor: Any, params: dict[str, Any]) -> Any:
        import torch.nn.functional as F

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

        interpolation = params.get("interpolation", "lanczos4")
        torch_mode = {
            "area": "area",
            "linear": "bilinear",
            "cubic": "bicubic",
            "lanczos4": "bicubic",
        }.get(interpolation, "bicubic")
        if torch_mode == "area":
            return F.interpolate(tensor, size=target_size, mode=torch_mode)
        return F.interpolate(tensor, size=target_size, mode=torch_mode, align_corners=False).clamp(0.0, 1.0)

    def _apply_tensor_crop(self, tensor: Any, params: dict[str, Any]) -> Any:
        x = max(0, int(params.get("x", 0)))
        y = max(0, int(params.get("y", 0)))
        width = int(params.get("width", tensor.shape[-1]))
        height = int(params.get("height", tensor.shape[-2]))
        h = int(tensor.shape[-2])
        w = int(tensor.shape[-1])
        x2 = min(w, x + width)
        y2 = min(h, y + height)
        return tensor[:, :, y:y2, x:x2]

    def _apply_tensor_pad(self, tensor: Any, params: dict[str, Any]) -> Any:
        import torch

        top = int(params.get("top", 0))
        bottom = int(params.get("bottom", 0))
        left = int(params.get("left", 0))
        right = int(params.get("right", 0))
        if top == bottom == left == right == 0:
            return tensor

        color = self._parse_hex_color(params.get("color", "#000000"))
        n, c, h, w = tensor.shape
        out = torch.empty(
            (n, c, h + top + bottom, w + left + right),
            dtype=tensor.dtype,
            device=tensor.device,
        )
        fill = torch.tensor(color[:c], dtype=tensor.dtype, device=tensor.device).view(1, c, 1, 1) / 255.0
        out.copy_(fill.expand_as(out))
        out[:, :, top : top + h, left : left + w] = tensor
        return out

    def _apply_tensor_sharpen(self, tensor: Any, params: dict[str, Any]) -> Any:
        import torch
        import torch.nn.functional as F

        amount = float(params.get("amount", 0.5))
        if amount <= 0:
            return tensor

        sigma = 3.0
        radius = int(round(sigma * 3))
        coords = torch.arange(-radius, radius + 1, dtype=tensor.dtype, device=tensor.device)
        kernel_1d = torch.exp(-(coords**2) / (2 * sigma * sigma))
        kernel_1d = kernel_1d / kernel_1d.sum()
        channels = int(tensor.shape[1])
        kernel_h = kernel_1d.view(1, 1, 1, -1).expand(channels, 1, 1, -1)
        kernel_v = kernel_1d.view(1, 1, -1, 1).expand(channels, 1, -1, 1)
        padded = F.pad(tensor, (radius, radius, 0, 0), mode="replicate")
        blurred = F.conv2d(padded, kernel_h, groups=channels)
        padded = F.pad(blurred, (0, 0, radius, radius), mode="replicate")
        blurred = F.conv2d(padded, kernel_v, groups=channels)
        return (tensor * (1.0 + amount) - blurred * amount).clamp(0.0, 1.0)

    def _apply_tensor_denoise(self, tensor: Any, params: dict[str, Any]) -> Any:
        strength = float(params.get("strength", 10))
        color_strength = float(params.get("colorStrength", 10))
        if strength <= 0 and color_strength <= 0:
            return tensor
        raise RuntimeError("frame_filter_chain denoise does not support tensor processing.")

    def _apply_tensor_color(self, tensor: Any, params: dict[str, Any]) -> Any:
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
            if tensor.shape[1] == 3:
                tensor = rgb
            else:
                tensor = torch.cat([rgb, tensor[:, 3:]], dim=1)

        return tensor.clamp(0.0, 1.0)


def _backend_name(backend: Any) -> str:
    get_name = getattr(backend, "get_name", None)
    if callable(get_name):
        try:
            return str(get_name()).lower()
        except Exception:
            return ""
    return ""
