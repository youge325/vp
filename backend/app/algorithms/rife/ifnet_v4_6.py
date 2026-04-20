"""RIFE v4.6 模型定义。

特点：LeakyReLU 激活、ResConv 残差卷积、无 Head 编码器、4 级 IFBlock、
PixelShuffle 上采样、lastconv 输出 4*6=24 通道、支持 ensemble。

与 v4.5 的差异：lastconv 输出 4*6（多 1 个通道给 mask）。

参考 vs-rife 的 IFNet_HDv3_v4_6.py 实现。
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from .warplayer import warp


def conv(
    in_planes: int,
    out_planes: int,
    kernel_size: int = 3,
    stride: int = 1,
    padding: int = 1,
    dilation: int = 1,
) -> nn.Sequential:
    """带 LeakyReLU 激活的卷积层。"""
    return nn.Sequential(
        nn.Conv2d(
            in_planes,
            out_planes,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
            bias=True,
        ),
        nn.LeakyReLU(0.2, True),
    )


class ResConv(nn.Module):
    """可学习缩放的残差卷积块。"""

    def __init__(self, c: int, dilation: int = 1):
        super(ResConv, self).__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, dilation, dilation=dilation, groups=1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    """中间帧估计块（v4.6 风格）。

    ResConv + PixelShuffle 上采样，lastconv 输出 4*6=24 通道，输出 (flow, mask) 2 元组。
    """

    def __init__(self, in_planes: int, c: int = 64):
        super(IFBlock, self).__init__()
        self.conv0 = nn.Sequential(
            conv(in_planes, c // 2, 3, 2, 1),
            conv(c // 2, c, 3, 2, 1),
        )
        self.convblock = nn.Sequential(
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
        )
        self.lastconv = nn.Sequential(
            nn.ConvTranspose2d(c, 4 * 6, 4, 2, 1),
            nn.PixelShuffle(2),
        )

    def forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1) -> tuple:
        x = F.interpolate(x, scale_factor=1.0 / scale, mode="bilinear")
        if flow is not None:
            flow = F.interpolate(flow, scale_factor=1.0 / scale, mode="bilinear") / scale
            x = torch.cat((x, flow), 1)
        feat = self.conv0(x)
        feat = self.convblock(feat)
        tmp = self.lastconv(feat)
        tmp = F.interpolate(tmp, scale_factor=scale, mode="bilinear")
        flow = tmp[:, :4] * scale
        mask = tmp[:, 4:5]
        return flow, mask


class IFNet(nn.Module):
    """RIFE v4.6 主网络。

    4 级 IFBlock（ResConv + PixelShuffle），无 Head 编码器，支持 ensemble。
    lastconv 输出 4*6=24 通道。
    """

    def __init__(self, scale: float = 1, ensemble: bool = False):
        super(IFNet, self).__init__()
        self.block0 = IFBlock(7, c=192)
        self.block1 = IFBlock(8 + 4, c=128)
        self.block2 = IFBlock(8 + 4, c=96)
        self.block3 = IFBlock(8 + 4, c=64)
        self.scale_list = [8 / scale, 4 / scale, 2 / scale, 1 / scale]
        self.ensemble = ensemble

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
        flow_list = []
        merged = []
        mask_list = []
        warped_img0 = img0
        warped_img1 = img1
        flow = None
        mask = None
        block = [self.block0, self.block1, self.block2, self.block3]
        for i in range(4):
            if flow is None:
                flow, mask = block[i](torch.cat((img0, img1, timestep), 1), None, scale=self.scale_list[i])
                if self.ensemble:
                    f1, m1 = block[i](
                        torch.cat((img1, img0, 1 - timestep), 1),
                        None,
                        scale=self.scale_list[i],
                    )
                    flow = (flow + torch.cat((f1[:, 2:4], f1[:, :2]), 1)) / 2
                    mask = (mask + (-m1)) / 2
            else:
                f0, m0 = block[i](
                    torch.cat((warped_img0, warped_img1, timestep, mask), 1),
                    flow,
                    scale=self.scale_list[i],
                )
                if self.ensemble:
                    f1, m1 = block[i](
                        torch.cat((warped_img1, warped_img0, 1 - timestep, -mask), 1),
                        torch.cat((flow[:, 2:4], flow[:, :2]), 1),
                        scale=self.scale_list[i],
                    )
                    f0 = (f0 + torch.cat((f1[:, 2:4], f1[:, :2]), 1)) / 2
                    m0 = (m0 + (-m1)) / 2
                flow = flow + f0
                mask = mask + m0
            mask_list.append(mask)
            flow_list.append(flow)
            warped_img0 = warp(img0, flow[:, :2], tenFlow_div, backwarp_tenGrid)
            warped_img1 = warp(img1, flow[:, 2:4], tenFlow_div, backwarp_tenGrid)
            merged.append((warped_img0, warped_img1))
        mask_list[3] = torch.sigmoid(mask_list[3])
        return merged[3][0] * mask_list[3] + merged[3][1] * (1 - mask_list[3])
