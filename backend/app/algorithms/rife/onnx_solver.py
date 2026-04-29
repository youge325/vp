"""RIFE ONNX Runtime 推理求解器。

使用导出的 ONNX 模型进行帧对插值，输入输出均为 numpy ndarray。
"""

import os
from typing import Optional

import numpy as np

from app.utils.logger import get_logger
from app.algorithms.onnx_models import resolve_onnx_model_path
from .model_loader import get_model_dir, MODEL_CONFIGS

logger = get_logger(__name__)


def _np_pad_frame(img: np.ndarray, modulo: int) -> tuple[np.ndarray, tuple]:
    """numpy 版本 pad_frame。"""
    _, _, h, w = img.shape
    ph = ((h - 1) // modulo + 1) * modulo
    pw = ((w - 1) // modulo + 1) * modulo
    padding = (0, pw - w, 0, ph - h)
    if any(p > 0 for p in padding):
        img = np.pad(
            img,
            pad_width=((0, 0), (0, 0), (0, padding[3]), (0, padding[1])),
            mode="constant",
        )
    return img, padding


def _np_unpad_frame(img: np.ndarray, padding: tuple, orig_h: int, orig_w: int) -> np.ndarray:
    """numpy 版本 unpad_frame。"""
    if any(p > 0 for p in padding):
        return img[:, :, :orig_h, :orig_w]
    return img


def _np_create_backwarp_grid(height: int, width: int) -> np.ndarray:
    """numpy 版本 create_backwarp_grid。"""
    tenHorizontal = np.linspace(-1.0, 1.0, width, dtype=np.float32).reshape(1, 1, 1, width)
    tenHorizontal = np.broadcast_to(tenHorizontal, (1, 1, height, width))
    tenVertical = np.linspace(-1.0, 1.0, height, dtype=np.float32).reshape(1, 1, height, 1)
    tenVertical = np.broadcast_to(tenVertical, (1, 1, height, width))
    return np.concatenate([tenHorizontal, tenVertical], axis=1)


def _np_create_flow_div(height: int, width: int) -> np.ndarray:
    """numpy 版本 create_flow_div。"""
    return np.array([(width - 1.0) / 2.0, (height - 1.0) / 2.0], dtype=np.float32)


class RIFEONNXSolver:
    """RIFE ONNX Runtime 推理求解器。

    用法:
        solver = RIFEONNXSolver(model_version="4.25")
        mid_frame = solver.interpolate(img0_np, img1_np, timestep=0.5)

    其中 img0_np/img1_np 为形状 (1, 3, H, W)、值域 [0,1] 的 float32 numpy 数组。
    返回同样形状的 numpy 数组。
    """

    def __init__(
        self,
        model_version: str = "4.25",
        model_dir: Optional[str] = None,
        onnx_model: Optional[str] = None,
    ):
        import onnxruntime as ort

        self._model_version = model_version
        self._config = MODEL_CONFIGS[model_version]
        self._modulo = self._config["modulo"]

        model_dir = model_dir or get_model_dir()
        if onnx_model:
            onnx_path = str(resolve_onnx_model_path("interpolation", onnx_model, model_dir))
        else:
            onnx_path = os.path.join(model_dir, "interpolation", f"rife_v{model_version}.onnx")
            legacy_path = os.path.join(model_dir, f"rife_v{model_version}.onnx")
            if not os.path.isfile(onnx_path) and os.path.isfile(legacy_path):
                onnx_path = legacy_path
            if not os.path.isfile(onnx_path):
                raise FileNotFoundError(
                    f"ONNX 模型文件未找到: {onnx_path}。"
                    f"请将补帧 ONNX 模型放入 {os.path.join(model_dir, 'interpolation')}，"
                    f"或运行 export_rife_to_onnx(model_version='{model_version}') 导出模型"
                )

        # 优先使用 GPU EP，回退到 CPU
        providers = ort.get_available_providers()
        logger.info(f"ONNX Runtime 可用 providers: {providers}")
        self._session = ort.InferenceSession(onnx_path, providers=providers)

        self._input_names = {inp.name for inp in self._session.get_inputs()}
        self._output_names = [out.name for out in self._session.get_outputs()]

        # 缓存
        self._cached_size: Optional[tuple[int, int]] = None
        self._backwarp_grid: Optional[np.ndarray] = None
        self._flow_div: Optional[np.ndarray] = None

        logger.info(
            f"RIFEONNXSolver 初始化完成: v{model_version}, "
            f"model={onnx_path}, providers={self._session.get_providers()}, modulo={self._modulo}"
        )

    def _ensure_grid_cache(self, height: int, width: int):
        if self._cached_size == (height, width):
            return
        self._backwarp_grid = _np_create_backwarp_grid(height, width)
        self._flow_div = _np_create_flow_div(height, width)
        self._cached_size = (height, width)

    def interpolate(
        self,
        img0: np.ndarray,
        img1: np.ndarray,
        timestep: float = 0.5,
    ) -> np.ndarray:
        """对两帧进行插值，生成中间帧。

        参数:
            img0: 前一帧，形状 (1, 3, H, W)，值域 [0, 1]，float32
            img1: 后一帧，形状 (1, 3, H, W)，值域 [0, 1]，float32
            timestep: 插值时间步，默认 0.5

        返回:
            中间帧，形状 (1, 3, H, W)，值域 [0, 1]，float32
        """
        orig_h, orig_w = img0.shape[2], img0.shape[3]

        # Padding
        img0_padded, padding = _np_pad_frame(img0, self._modulo)
        img1_padded, _ = _np_pad_frame(img1, self._modulo)
        padded_h, padded_w = img0_padded.shape[2], img0_padded.shape[3]

        self._ensure_grid_cache(padded_h, padded_w)

        t = np.full((1, 1, padded_h, padded_w), timestep, dtype=np.float32)

        # 构造输入 feed
        feed = {
            "img0": img0_padded,
            "img1": img1_padded,
            "timestep": t,
            "tenFlow_div": self._flow_div,
            "flow_div": self._flow_div,
            "backwarp_tenGrid": self._backwarp_grid,
            "backwarp_grid": self._backwarp_grid,
            "grid": self._backwarp_grid,
        }
        # 仅传递模型实际需要的输入（防御性编程）
        feed = {k: v for k, v in feed.items() if k in self._input_names}

        output = self._session.run(self._output_names, feed)[0]

        # Unpad
        output = _np_unpad_frame(output, padding, orig_h, orig_w)

        return np.clip(output, 0.0, 1.0).astype(np.float32)

    def interpolate_multi(
        self,
        img0: np.ndarray,
        img1: np.ndarray,
        multi: int = 2,
    ) -> list[np.ndarray]:
        """多倍插值，生成 (multi-1) 个中间帧。"""
        results = []
        for j in range(1, multi):
            t = j / multi
            mid = self.interpolate(img0, img1, timestep=t)
            results.append(mid)
        return results

    def clear_cache(self):
        """清除网格缓存。"""
        self._cached_size = None
        self._backwarp_grid = None
        self._flow_div = None
