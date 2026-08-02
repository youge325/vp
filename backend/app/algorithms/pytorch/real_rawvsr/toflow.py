"""Native-PyTorch TOFlow inference network without MMCV runtime dependencies."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

from app.algorithms.pytorch.real_rawvsr.tensor_ops import flow_warp


class _ConvBlock(nn.Module):
    """Checkpoint-compatible subset of MMCV ConvModule."""

    def __init__(self, in_channels: int, out_channels: int, *, normalized: bool) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 7, 1, 3, bias=not normalized)
        self.bn = nn.BatchNorm2d(out_channels) if normalized else None
        self.activate = nn.ReLU(inplace=True) if normalized else None

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        value = self.conv(value)
        if self.bn is not None:
            value = self.bn(value)
        return self.activate(value) if self.activate is not None else value


class _BasicModule(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        channels = ((8, 32), (32, 64), (64, 32), (32, 16), (16, 2))
        self.basic_module = nn.Sequential(
            *(
                _ConvBlock(in_channels, out_channels, normalized=index < len(channels) - 1)
                for index, (in_channels, out_channels) in enumerate(channels)
            )
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.basic_module(value)


class _SpyNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.basic_module = nn.ModuleList(_BasicModule() for _ in range(4))

    def forward(self, reference: torch.Tensor, support: torch.Tensor) -> torch.Tensor:
        batch, _, height, width = reference.shape
        reference_pyramid = [reference]
        support_pyramid = [support]
        for _ in range(3):
            reference_pyramid.insert(
                0,
                F.avg_pool2d(reference_pyramid[0], kernel_size=2, stride=2, count_include_pad=False),
            )
            support_pyramid.insert(
                0,
                F.avg_pool2d(support_pyramid[0], kernel_size=2, stride=2, count_include_pad=False),
            )
        flow = reference.new_zeros(batch, 2, height // 16, width // 16)
        for index, module in enumerate(self.basic_module):
            flow_up = F.interpolate(flow, scale_factor=2, mode="bilinear", align_corners=True) * 2.0
            warped = flow_warp(support_pyramid[index], flow_up.permute(0, 2, 3, 1))
            flow = flow_up + module(torch.cat((reference_pyramid[index], warped, flow_up), dim=1))
        return flow


class _ToFlowNet(nn.Module):
    def __init__(self, *, scale: int, frames: int = 5) -> None:
        super().__init__()
        if scale not in {2, 3, 4}:
            raise ValueError(f"TOFlow scale must be 2, 3, or 4; got {scale}.")
        self.ref_idx = frames // 2
        self.frames = frames
        self.scale = scale
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))
        self.spynet = _SpyNet()
        self.conv1 = nn.Conv2d(3 * frames, 64, 9, 1, 4)
        self.conv2 = nn.Conv2d(64, 64, 9, 1, 4)
        self.conv3 = nn.Conv2d(64, 64, 1)
        self.conv4 = nn.Conv2d(64, 3, 1)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, frames: torch.Tensor) -> torch.Tensor:
        batch, count, channels, height, width = frames.shape
        upscaled = F.interpolate(
            frames.reshape(-1, channels, height, width),
            scale_factor=self.scale,
            mode="bicubic",
            align_corners=False,
        ).view(batch, count, channels, height * self.scale, width * self.scale)
        normalized = ((upscaled.reshape(-1, 3, height * self.scale, width * self.scale) - self.mean) / self.std).view(
            batch, count, 3, height * self.scale, width * self.scale
        )
        reference = normalized[:, self.ref_idx]
        aligned: list[torch.Tensor] = []
        for index in range(self.frames):
            if index == self.ref_idx:
                aligned.append(reference)
            else:
                support = normalized[:, index]
                flow = self.spynet(reference, support)
                aligned.append(flow_warp(support, flow.permute(0, 2, 3, 1)))
        reconstruction = torch.stack(aligned, dim=1).reshape(
            batch, self.frames * 3, height * self.scale, width * self.scale
        )
        reconstruction = self.relu(self.conv1(reconstruction))
        reconstruction = self.relu(self.conv2(reconstruction))
        reconstruction = self.relu(self.conv3(reconstruction))
        return (self.conv4(reconstruction) + reference) * self.std + self.mean


def load_toflow_model(scale: int, weight_path: str) -> tuple[Any, nn.Module]:
    from safetensors.torch import load_file

    if not torch.cuda.is_available():
        raise RuntimeError("Real-RawVSR TOFlow requires an available NVIDIA CUDA device.")
    model = _ToFlowNet(scale=scale)
    model.load_state_dict(load_file(weight_path, device="cpu"), strict=True)
    model.eval().to(torch.device("cuda"))
    return torch, model


__all__ = ["load_toflow_model"]
