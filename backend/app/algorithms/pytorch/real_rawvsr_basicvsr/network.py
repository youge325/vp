"""Minimal inference-only BasicVSR port preserving the upstream checkpoint keys.

Derived from Real-RawVSR/OpenMMLab BasicVSR under CC BY-NC-SA 4.0. Training,
registry, logging, MMCV, and checkpoint-loading facades are intentionally absent.
"""

# Copyright (c) OpenMMLab. All rights reserved.

from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.nn import functional as F


def _flow_warp(
    value: torch.Tensor,
    flow: torch.Tensor,
    *,
    padding_mode: str = "zeros",
) -> torch.Tensor:
    if value.shape[-2:] != flow.shape[1:3]:
        raise ValueError("BasicVSR flow and feature spatial dimensions do not match.")
    height, width = value.shape[-2:]
    grid_y, grid_x = torch.meshgrid(
        torch.arange(height, device=value.device),
        torch.arange(width, device=value.device),
        indexing="ij",
    )
    grid = torch.stack((grid_x, grid_y), dim=2).to(dtype=value.dtype)
    grid_flow = grid + flow
    grid_x_normalized = 2.0 * grid_flow[..., 0] / max(width - 1, 1) - 1.0
    grid_y_normalized = 2.0 * grid_flow[..., 1] / max(height - 1, 1) - 1.0
    normalized = torch.stack((grid_x_normalized, grid_y_normalized), dim=3)
    return F.grid_sample(
        value,
        normalized,
        mode="bilinear",
        padding_mode=padding_mode,
        align_corners=True,
    )


class _ConvModule(nn.Module):
    """The parameter-bearing subset of MMCV ConvModule used by SPyNet."""

    def __init__(self, in_channels: int, out_channels: int, *, activate: bool = True) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 7, 1, 3)
        self.activate = nn.ReLU(inplace=True) if activate else nn.Identity()

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.activate(self.conv(value))


class _ResidualBlockNoBN(nn.Module):
    def __init__(self, mid_channels: int = 64) -> None:
        super().__init__()
        self.res_scale = 1.0
        self.conv1 = nn.Conv2d(mid_channels, mid_channels, 3, 1, 1)
        self.conv2 = nn.Conv2d(mid_channels, mid_channels, 3, 1, 1)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return value + self.conv2(self.relu(self.conv1(value))) * self.res_scale


class _PixelShufflePack(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, scale_factor: int) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.scale_factor = scale_factor
        self.upsample_conv = nn.Conv2d(in_channels, out_channels * scale_factor**2, 3, padding=1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return F.pixel_shuffle(self.upsample_conv(value), self.scale_factor)


class _ResidualBlocksWithInputConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int = 64, num_blocks: int = 30) -> None:
        super().__init__()
        self.main = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, 1, 1),
            nn.LeakyReLU(negative_slope=0.1, inplace=True),
            nn.Sequential(*(_ResidualBlockNoBN(out_channels) for _ in range(num_blocks))),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.main(value)


class _SPyNetBasicModule(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        channels = ((8, 32), (32, 64), (64, 32), (32, 16), (16, 2))
        self.basic_module = nn.Sequential(
            *(
                _ConvModule(in_channels, out_channels, activate=index < len(channels) - 1)
                for index, (in_channels, out_channels) in enumerate(channels)
            )
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.basic_module(value)


class _SPyNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.basic_module = nn.ModuleList(_SPyNetBasicModule() for _ in range(6))
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def _compute_flow(self, reference: torch.Tensor, support: torch.Tensor) -> torch.Tensor:
        batch, _, height, width = reference.shape
        reference_pyramid = [(reference - self.mean) / self.std]
        support_pyramid = [(support - self.mean) / self.std]
        for _ in range(5):
            reference_pyramid.append(F.avg_pool2d(reference_pyramid[-1], 2, 2, count_include_pad=False))
            support_pyramid.append(F.avg_pool2d(support_pyramid[-1], 2, 2, count_include_pad=False))
        reference_pyramid.reverse()
        support_pyramid.reverse()
        flow = reference.new_zeros(batch, 2, height // 32, width // 32)
        for level, reference_level in enumerate(reference_pyramid):
            flow_up = (
                flow
                if level == 0
                else F.interpolate(
                    flow,
                    scale_factor=2,
                    mode="bilinear",
                    align_corners=True,
                )
                * 2.0
            )
            warped = _flow_warp(
                support_pyramid[level],
                flow_up.permute(0, 2, 3, 1),
                padding_mode="border",
            )
            flow = flow_up + self.basic_module[level](torch.cat((reference_level, warped, flow_up), dim=1))
        return flow

    def forward(self, reference: torch.Tensor, support: torch.Tensor) -> torch.Tensor:
        height, width = reference.shape[2:4]
        height_up = ((height + 31) // 32) * 32
        width_up = ((width + 31) // 32) * 32
        resized_reference = F.interpolate(reference, (height_up, width_up), mode="bilinear", align_corners=False)
        resized_support = F.interpolate(support, (height_up, width_up), mode="bilinear", align_corners=False)
        flow = F.interpolate(
            self._compute_flow(resized_reference, resized_support),
            (height, width),
            mode="bilinear",
            align_corners=False,
        )
        flow[:, 0] *= width / width_up
        flow[:, 1] *= height / height_up
        return flow


class _BasicVSRNet(nn.Module):
    """RGB BasicVSR network with 2x, 3x, and 4x checkpoint-compatible heads."""

    def __init__(self, *, scale: int, mid_channels: int = 64, num_blocks: int = 30) -> None:
        super().__init__()
        if scale not in {2, 3, 4}:
            raise ValueError(f"BasicVSR scale must be 2, 3, or 4; got {scale}.")
        self.mid_channels = mid_channels
        self.spynet = _SPyNet()
        self.backward_resblocks = _ResidualBlocksWithInputConv(mid_channels + 3, mid_channels, num_blocks)
        self.forward_resblocks = _ResidualBlocksWithInputConv(mid_channels + 3, mid_channels, num_blocks)
        self.scale = scale
        self.fusion = nn.Conv2d(mid_channels * 2, mid_channels, 1)
        if scale == 4:
            self.upsample1 = _PixelShufflePack(mid_channels, mid_channels, 2)
            self.upsample2 = _PixelShufflePack(mid_channels, 64, 2)
        else:
            self.upsample = _PixelShufflePack(mid_channels, 64, scale)
        self.conv_hr = nn.Conv2d(64, 64, 3, 1, 1)
        self.conv_last = nn.Conv2d(64, 3, 3, 1, 1)
        self.img_upsample = nn.Upsample(scale_factor=scale, mode="bilinear", align_corners=False)
        self.lrelu = nn.LeakyReLU(negative_slope=0.1, inplace=True)
        self.is_mirror_extended = False

    def _compute_flow(self, frames: torch.Tensor) -> tuple[torch.Tensor | None, torch.Tensor]:
        batch, count, channels, height, width = frames.shape
        previous = frames[:, :-1].reshape(-1, channels, height, width)
        following = frames[:, 1:].reshape(-1, channels, height, width)
        backward = self.spynet(previous, following).view(batch, count - 1, 2, height, width)
        forward = (
            None
            if self.is_mirror_extended
            else self.spynet(following, previous).view(
                batch,
                count - 1,
                2,
                height,
                width,
            )
        )
        return forward, backward

    def forward(self, frames: torch.Tensor) -> torch.Tensor:
        batch, count, _, height, width = frames.shape
        if height < 64 or width < 64:
            raise ValueError(f"BasicVSR input must be at least 64x64; got {width}x{height}.")
        self.is_mirror_extended = False
        if count % 2 == 0:
            first, second = torch.chunk(frames, 2, dim=1)
            self.is_mirror_extended = bool(torch.norm(first - second.flip(1)) == 0)
        forward_flow, backward_flow = self._compute_flow(frames)
        propagated = frames.new_zeros(batch, self.mid_channels, height, width)
        outputs: list[torch.Tensor] = []
        for index in range(count - 1, -1, -1):
            if index < count - 1:
                propagated = _flow_warp(propagated, backward_flow[:, index].permute(0, 2, 3, 1))
            propagated = self.backward_resblocks(torch.cat((frames[:, index], propagated), dim=1))
            outputs.append(propagated)
        outputs.reverse()
        propagated = torch.zeros_like(propagated)
        for index in range(count):
            current = frames[:, index]
            if index > 0:
                flow = forward_flow[:, index - 1] if forward_flow is not None else backward_flow[:, -index]
                propagated = _flow_warp(propagated, flow.permute(0, 2, 3, 1))
            propagated = self.forward_resblocks(torch.cat((current, propagated), dim=1))
            output = self.lrelu(self.fusion(torch.cat((outputs[index], propagated), dim=1)))
            if self.scale == 4:
                output = self.lrelu(self.upsample1(output))
                output = self.lrelu(self.upsample2(output))
            else:
                output = self.lrelu(self.upsample(output))
            output = self.conv_last(self.lrelu(self.conv_hr(output)))
            outputs[index] = output + self.img_upsample(current)
        return torch.stack(outputs, dim=1)


def load_basicvsr_model(*, scale: int, weight_path: str) -> tuple[Any, nn.Module]:
    """Strictly load a SafeTensors inference checkpoint onto CUDA."""
    from safetensors.torch import load_file

    if not torch.cuda.is_available():
        raise RuntimeError("Real-RawVSR BasicVSR requires an available NVIDIA CUDA device.")
    model = _BasicVSRNet(scale=scale)
    state = load_file(weight_path, device="cpu")
    model.load_state_dict(state, strict=True)
    model.eval().to(torch.device("cuda"))
    return torch, model


__all__ = ["load_basicvsr_model"]
