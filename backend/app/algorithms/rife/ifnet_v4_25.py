"""RIFE v4.25 模型定义。

包含 Head 编码器、ResConv 残差卷积、IFBlock 中间帧估计块、IFNet 主网络。
参考 vs-rife 的 IFNet_HDv3_v4_25.py 实现。
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


class Head(nn.Module):
    """特征编码头，将 3 通道 RGB 图像编码为 4 通道特征图。

    结构: Conv2d(3→16, stride=2) → Conv2d(16→16) → Conv2d(16→16) → ConvTranspose2d(16→4)
    """

    def __init__(self):
        super(Head, self).__init__()
        self.cnn0 = nn.Conv2d(3, 16, 3, 2, 1)
        self.cnn1 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn2 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn3 = nn.ConvTranspose2d(16, 4, 4, 2, 1)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x: torch.Tensor, feat: bool = False):
        x = x.clamp(0.0, 1.0)
        x0 = self.cnn0(x)
        x = self.relu(x0)
        x1 = self.cnn1(x)
        x = self.relu(x1)
        x2 = self.cnn2(x)
        x = self.relu(x2)
        x3 = self.cnn3(x)
        if feat:
            return [x0, x1, x2, x3]
        return x3


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
    """中间帧估计块。

    将输入下采样 2 级后通过 8 个 ResConv 残差块，再上采样回原分辨率，
    输出光流增量 (4ch)、mask (1ch)、特征 (8ch)。
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
            nn.ConvTranspose2d(c, 4 * 13, 4, 2, 1),
            nn.PixelShuffle(2),
        )

    def forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1) -> tuple:
        """
        参数:
            x: 输入特征
            flow: 前一级光流（首级为 None）
            scale: 缩放系数

        返回:
            (flow, mask, feat) 元组
        """
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
        feat = tmp[:, 5:]
        return flow, mask, feat


class IFNet(nn.Module):
    """RIFE v4.25 主网络。

    5 级 IFBlock 级联细化光流：
    - block0: 首级估计，输入 (img0, img1, f0, f1, timestep)
    - block1~4: 级联细化，输入 (warped_img0, warped_img1, wf0, wf1, timestep, mask, feat)

    v4.25 特点：
    - Head 编码器输出 4 通道特征 (encode_channel=4)
    - modulo=64（padding 到 64 的倍数）
    - 不支持 ensemble
    """

    def __init__(self, scale: float = 1, ensemble: bool = False):
        super(IFNet, self).__init__()
        if ensemble:
            raise ValueError("RIFE v4.25 不支持 ensemble 模式")

        self.block0 = IFBlock(7 + 8, c=192)  # img0(3)+img1(3)+timestep(1) + f0(4)+f1(4) = 15
        self.block1 = IFBlock(
            8 + 4 + 8 + 8, c=128
        )  # warped0(3)+warped1(3)+timestep(1)+mask(1) + wf0(4)+wf1(4)+feat(8) = 28
        self.block2 = IFBlock(8 + 4 + 8 + 8, c=96)
        self.block3 = IFBlock(8 + 4 + 8 + 8, c=64)
        self.block4 = IFBlock(8 + 4 + 8 + 8, c=32)
        self.encode = Head()
        self.scale_list = [16 / scale, 8 / scale, 4 / scale, 2 / scale, 1 / scale]

    def forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    ) -> torch.Tensor:
        """
        前向推理：输入两帧图像，输出中间帧。

        参数:
            img0: 前一帧图像，形状 (1, 3, H, W)，值域 [0, 1]
            img1: 后一帧图像，形状 (1, 3, H, W)，值域 [0, 1]
            timestep: 时间步，形状 (1, 1, H, W)，值域 [0, 1]
            tenFlow_div: 光流归一化除数，形状 (2,)
            backwarp_tenGrid: 基础采样网格，形状 (1, 2, H, W)
            f0: img0 的 Head 编码特征，形状 (1, 4, H, W)
            f1: img1 的 Head 编码特征，形状 (1, 4, H, W)

        返回:
            插值中间帧，形状 (1, 3, H, W)，值域 [0, 1]
        """
        img0 = img0.clamp(0.0, 1.0)
        img1 = img1.clamp(0.0, 1.0)

        flow = None
        mask = None
        warped_img0 = img0
        warped_img1 = img1

        block = [self.block0, self.block1, self.block2, self.block3, self.block4]

        for i in range(5):
            if flow is None:
                # 首级：拼接原始图像 + 编码特征 + 时间步
                flow, mask, feat = block[i](
                    torch.cat((img0, img1, f0, f1, timestep), 1),
                    None,
                    scale=self.scale_list[i],
                )
            else:
                # 后续级：warp 特征后拼接
                wf0 = warp(f0, flow[:, :2], tenFlow_div, backwarp_tenGrid)
                wf1 = warp(f1, flow[:, 2:4], tenFlow_div, backwarp_tenGrid)
                fd, m0, feat = block[i](
                    torch.cat((warped_img0, warped_img1, wf0, wf1, timestep, mask, feat), 1),
                    flow,
                    scale=self.scale_list[i],
                )
                mask = m0
                flow = flow + fd

            # 用当前光流 warp 原始图像
            warped_img0 = warp(img0, flow[:, :2], tenFlow_div, backwarp_tenGrid)
            warped_img1 = warp(img1, flow[:, 2:4], tenFlow_div, backwarp_tenGrid)

        # 融合：基于 mask 的加权混合
        mask = torch.sigmoid(mask)
        return warped_img0 * mask + warped_img1 * (1 - mask)
