"""光流后向变形函数（线程安全版）。

参考 vs-rife 实现：将 tenFlow_div 和 backwarp_tenGrid 作为参数传入，
避免使用全局缓存，确保线程安全。
"""

import torch
import torch.nn.functional as F


def warp(
    tenInput: torch.Tensor,
    tenFlow: torch.Tensor,
    tenFlow_div: torch.Tensor,
    backwarp_tenGrid: torch.Tensor,
) -> torch.Tensor:
    """
    使用光流对输入进行后向变形（backward warp）。

    参数:
        tenInput: 输入特征图，形状 (N, C, H, W)
        tenFlow: 光流场，形状 (N, 2, H, W)
        tenFlow_div: 归一化除数，形状 (2,)，值为 [(W-1)/2, (H-1)/2]
        backwarp_tenGrid: 基础采样网格，形状 (1, 2, H, W)

    返回:
        变形后的特征图，形状与 tenInput 相同
    """
    dtype = tenInput.dtype
    tenInput = tenInput.to(torch.float)
    tenFlow = tenFlow.to(torch.float)

    # 将光流归一化到 [-1, 1] 范围
    tenFlow = torch.cat([tenFlow[:, 0:1] / tenFlow_div[0], tenFlow[:, 1:2] / tenFlow_div[1]], 1)
    g = (backwarp_tenGrid + tenFlow).permute(0, 2, 3, 1)
    return F.grid_sample(
        input=tenInput,
        grid=g,
        mode="bilinear",
        padding_mode="border",
        align_corners=True,
    ).to(dtype)
