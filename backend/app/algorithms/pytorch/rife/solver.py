"""RIFE 推理求解器 — PyTorch 后端实现。

封装模型加载、帧对推理、padding/裁剪等细节。该模块顶层 ``import torch``,
所以仅在确实需要 PyTorch 推理时才 import (避免触发 cudnn DLL 加载)。
"""

from typing import Optional

import torch

from app.catalog.rife_models import HEAD_NONE
from .model_loader import (
    load_rife_model,
    create_backwarp_grid,
    create_flow_div,
    pad_frame,
    unpad_frame,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RIFESolver:
    """
    RIFE 推理求解器 — 封装模型加载和帧对插值推理。

    用法:
        solver = RIFESolver(model_version="4.25", scale=1.0, fp16=False)
        mid_frame = solver.interpolate(frame0_tensor, frame1_tensor, timestep=0.5)

    其中 frame0_tensor/frame1_tensor 为形状 (1, 3, H, W)、值域 [0,1] 的 float32 张量。
    """

    def __init__(
        self,
        model_version: str = "4.25",
        scale: float = 1.0,
        device: Optional[str] = None,
        fp16: bool = False,
        model_dir: Optional[str] = None,
        engine: str = "cuda",
    ):
        """
        参数:
            model_version: 模型版本（默认 "4.25"）
            scale: 处理分辨率缩放（1.0 原始，0.5 适用于 4K）
            device: 推理设备（默认自动选择）
            fp16: 是否使用半精度推理
            model_dir: 模型权重目录
            engine: 推理引擎（"cuda" 或 "tensorrt"，默认 "cuda"）
        """
        # 加载模型
        self._flownet, self._encode, spec = load_rife_model(
            model_version=model_version,
            scale=scale,
            device=device,
            fp16=fp16,
            model_dir=model_dir,
            engine=engine,
        )

        self._device = next(self._flownet.parameters()).device
        self._dtype = next(self._flownet.parameters()).dtype
        self._modulo = spec.modulo
        self._has_head = spec.head_type != HEAD_NONE

        # 缓存（同尺寸帧复用）
        self._cached_size = None
        self._backwarp_grid = None
        self._flow_div = None

        logger.info(
            f"RIFESolver 初始化完成: v{model_version}, "
            f"device={self._device}, dtype={self._dtype}, scale={scale}, "
            f"has_head={self._has_head}"
        )

    def _ensure_grid_cache(self, height: int, width: int):
        """确保采样网格和归一化除数已缓存（同尺寸帧复用）。"""
        if self._cached_size == (height, width):
            return
        self._backwarp_grid = create_backwarp_grid(height, width, self._device)
        self._flow_div = create_flow_div(height, width, self._device)
        self._cached_size = (height, width)

    def _encode_frame(self, img: torch.Tensor) -> torch.Tensor:
        """
        对帧进行 Head 编码。

        参数:
            img: 原始图像张量 (1, 3, H, W)

        返回:
            编码特征 (1, encode_channel, H, W)
        """
        return self._encode(img)

    @torch.inference_mode()
    def interpolate(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: float = 0.5,
    ) -> torch.Tensor:
        """
        对两帧进行插值，生成中间帧。

        根据 Head 类型自动选择推理路径：
        - 无 Head: flownet(img0, img1, t, flow_div, grid)
        - 有 Head: flownet(img0, img1, t, flow_div, grid, f0, f1)

        参数:
            img0: 前一帧，形状 (1, 3, H, W)，值域 [0, 1]，float32
            img1: 后一帧，形状 (1, 3, H, W)，值域 [0, 1]，float32
            timestep: 插值时间步，0.0=img0, 1.0=img1，默认 0.5

        返回:
            中间帧，形状 (1, 3, H, W)，值域 [0, 1]，float32
        """
        # 确保张量在正确设备和数据类型上
        img0 = img0.to(self._device, self._dtype)
        img1 = img1.to(self._device, self._dtype)

        _, _, orig_h, orig_w = img0.shape

        # Padding 到 modulo 的倍数
        img0_padded, padding = pad_frame(img0, self._modulo)
        img1_padded, _ = pad_frame(img1, self._modulo)

        _, _, padded_h, padded_w = img0_padded.shape

        # 确保网格缓存
        self._ensure_grid_cache(padded_h, padded_w)

        # 构造 timestep 张量
        t = torch.full(
            [1, 1, padded_h, padded_w],
            timestep,
            dtype=self._dtype,
            device=self._device,
        )

        # IFNet 推理（根据 Head 类型选择路径）
        if self._has_head:
            # 有 Head 编码器：先编码，再传 f0/f1
            f0 = self._encode_frame(img0_padded)
            f1 = self._encode_frame(img1_padded)
            output = self._flownet(
                img0_padded,
                img1_padded,
                t,
                self._flow_div,
                self._backwarp_grid,
                f0,
                f1,
            )
        else:
            # 无 Head 编码器：直接推理
            output = self._flownet(
                img0_padded,
                img1_padded,
                t,
                self._flow_div,
                self._backwarp_grid,
            )

        # 去除 padding
        output = unpad_frame(output, padding, orig_h, orig_w)

        # 转回 float32 输出
        return output.float().clamp(0.0, 1.0)
