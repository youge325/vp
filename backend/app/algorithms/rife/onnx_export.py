"""RIFE 模型 ONNX 导出工具。

将 PyTorch RIFE 模型导出为 ONNX 格式，支持动态输入尺寸。
"""

import os
from typing import Optional

import torch
import torch.nn as nn

from app.utils.logger import get_logger
from .model_loader import load_rife_model, get_model_dir, MODEL_CONFIGS, HEAD_NONE

logger = get_logger(__name__)


class RIFEExportWrapper(nn.Module):
    """包装 IFNet，将 encode + forward 合并为单一前向图。

    根据模型是否有 Head 编码器自动选择推理路径：
    - 无 Head: 直接调用 flownet(img0, img1, t, flow_div, grid)
    - 有 Head: 先 encode 再调用 flownet(..., f0, f1)
    """

    def __init__(self, flownet: nn.Module, has_head: bool):
        super().__init__()
        self.flownet = flownet
        self.has_head = has_head

    def forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    ) -> torch.Tensor:
        img0 = img0.clamp(0.0, 1.0)
        img1 = img1.clamp(0.0, 1.0)
        if self.has_head:
            f0 = self.flownet.encode(img0)
            f1 = self.flownet.encode(img1)
            return self.flownet(img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
        return self.flownet(img0, img1, timestep, tenFlow_div, backwarp_tenGrid)


def export_rife_to_onnx(
    model_version: str = "4.25",
    model_dir: Optional[str] = None,
    output_path: Optional[str] = None,
    opset_version: int = 17,
    dummy_size: tuple[int, int] = (256, 256),
    dynamo: bool = False,
) -> str:
    """将指定版本的 RIFE 模型导出为 ONNX。

    参数:
        model_version: 模型版本（默认 "4.25"）
        model_dir: 权重目录（默认 backend/models/）
        output_path: ONNX 输出路径（默认 backend/models/rife_v{version}.onnx）
        opset_version: ONNX opset 版本
        dummy_size: 导出时使用的 dummy 输入尺寸 (H, W)

    返回:
        导出的 ONNX 文件路径
    """
    if model_version not in MODEL_CONFIGS:
        raise ValueError(f"不支持的模型版本: {model_version}")

    config = MODEL_CONFIGS[model_version]
    has_head = config["head_type"] != HEAD_NONE

    # 加载 PyTorch 模型（CPU, float32）
    logger.info(f"加载 RIFE v{model_version} 用于 ONNX 导出 ...")
    flownet, _, _ = load_rife_model(
        model_version=model_version,
        model_dir=model_dir,
        device="cpu",
        fp16=False,
    )
    flownet.eval()

    wrapper = RIFEExportWrapper(flownet, has_head).eval()

    dummy_h, dummy_w = dummy_size
    dummy_img0 = torch.randn(1, 3, dummy_h, dummy_w)
    dummy_img1 = torch.randn(1, 3, dummy_h, dummy_w)
    dummy_t = torch.full((1, 1, dummy_h, dummy_w), 0.5)
    dummy_flow_div = torch.tensor(
        [(dummy_w - 1.0) / 2.0, (dummy_h - 1.0) / 2.0],
        dtype=torch.float32,
    )
    # 构造正确的采样网格（值域 [-1, 1]）
    tenHorizontal = torch.linspace(-1.0, 1.0, dummy_w).view(1, 1, 1, dummy_w).expand(-1, -1, dummy_h, -1)
    tenVertical = torch.linspace(-1.0, 1.0, dummy_h).view(1, 1, dummy_h, 1).expand(-1, -1, -1, dummy_w)
    dummy_grid = torch.cat([tenHorizontal, tenVertical], 1)

    if output_path is None:
        model_dir = model_dir or get_model_dir()
        output_path = os.path.join(model_dir, f"rife_v{model_version}.onnx")

    logger.info(f"导出 ONNX: {output_path} (opset={opset_version}, dummy={dummy_size}, dynamo={dynamo})")

    export_kwargs = {
        "input_names": ["img0", "img1", "timestep", "tenFlow_div", "backwarp_tenGrid"],
        "output_names": ["output"],
        "dynamic_axes": {
            "img0": {0: "batch", 2: "height", 3: "width"},
            "img1": {0: "batch", 2: "height", 3: "width"},
            "timestep": {0: "batch", 2: "height", 3: "width"},
            "backwarp_tenGrid": {0: "batch", 2: "height", 3: "width"},
            "output": {0: "batch", 2: "height", 3: "width"},
        },
        "opset_version": opset_version,
        "dynamo": dynamo,
    }

    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (dummy_img0, dummy_img1, dummy_t, dummy_flow_div, dummy_grid),
            output_path,
            **export_kwargs,
        )

    logger.info(f"ONNX 导出完成: {output_path}")
    return output_path
