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

logger = get_logger(__name__)

_INTERP_MAP: dict[str, int] = {}


def _ensure_cv2() -> None:
    """延迟加载 cv2，避免在服务端启动时强依赖。"""
    global _INTERP_MAP
    if _INTERP_MAP:
        return
    try:
        import cv2

        _INTERP_MAP.update(
            {
                "lanczos4": cv2.INTER_LANCZOS4,
                "cubic": cv2.INTER_CUBIC,
                "area": cv2.INTER_AREA,
                "linear": cv2.INTER_LINEAR,
            }
        )
    except ImportError as exc:
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
        if self._tensor_backend is None:
            return self.process_numpy(frame)
        np_frame = self._tensor_backend.tensor_to_numpy(frame)
        np_frame = self.process_numpy(np_frame)
        return self._tensor_backend.numpy_to_tensor(np_frame)

    def process_numpy(self, frame: np.ndarray) -> np.ndarray:
        """Apply the OpenCV filter chain directly on a CPU numpy frame."""
        return self._apply_filters(frame)

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
        import cv2

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
        import cv2

        top = int(params.get("top", 0))
        bottom = int(params.get("bottom", 0))
        left = int(params.get("left", 0))
        right = int(params.get("right", 0))
        if top == bottom == left == right == 0:
            return frame
        color_rgb = self._parse_hex_color(params.get("color", "#000000"))
        return cv2.copyMakeBorder(frame, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color_rgb)

    def _apply_sharpen(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        import cv2

        amount = float(params.get("amount", 0.5))
        if amount <= 0:
            return frame
        blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=3)
        return cv2.addWeighted(frame, 1.0 + amount, blurred, -amount, 0)

    def _apply_denoise(self, frame: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        import cv2

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
        import cv2

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
