"""Checkpoint-compatible DCNv2 layer backed by torchvision's CUDA operator."""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
from torch import nn
from torchvision.ops import deform_conv2d


def _pair(value: int | tuple[int, int]) -> tuple[int, int]:
    return value if isinstance(value, tuple) else (value, value)


class ModulatedDeformConvPack(nn.Module):
    """The parameter surface used by the upstream Real-RawVSR checkpoints."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        *,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        groups: int = 1,
        deformable_groups: int = 1,
        bias: bool = True,
        extra_offset_mask: bool = False,
    ) -> None:
        super().__init__()
        self.stride = _pair(stride)
        self.padding = _pair(padding)
        self.dilation = _pair(dilation)
        self.groups = groups
        self.deformable_groups = deformable_groups
        self.extra_offset_mask = extra_offset_mask
        kernel = _pair(kernel_size)
        self.weight = nn.Parameter(torch.empty(out_channels, in_channels // groups, *kernel))
        self.bias = nn.Parameter(torch.empty(out_channels)) if bias else None
        self.conv_offset_mask = nn.Conv2d(
            in_channels,
            deformable_groups * 3 * kernel[0] * kernel[1],
            kernel,
            stride=self.stride,
            padding=self.padding,
            bias=True,
        )
        self._reset_parameters(in_channels, kernel)

    def _reset_parameters(self, in_channels: int, kernel: tuple[int, int]) -> None:
        bound = 1.0 / math.sqrt(in_channels * kernel[0] * kernel[1])
        nn.init.uniform_(self.weight, -bound, bound)
        if self.bias is not None:
            nn.init.zeros_(self.bias)
        nn.init.zeros_(self.conv_offset_mask.weight)
        nn.init.zeros_(self.conv_offset_mask.bias)

    def forward(self, value: torch.Tensor | Sequence[torch.Tensor]) -> torch.Tensor:
        if self.extra_offset_mask:
            if not isinstance(value, Sequence) or len(value) != 2:
                raise ValueError("DCNv2 with extra_offset_mask requires [input, offset_features].")
            input_tensor, offset_features = value
        else:
            if not isinstance(value, torch.Tensor):
                raise ValueError("DCNv2 without extra_offset_mask requires a tensor input.")
            input_tensor = value
            offset_features = value
        offset_y, offset_x, mask = torch.chunk(self.conv_offset_mask(offset_features), 3, dim=1)
        offset = torch.cat((offset_y, offset_x), dim=1)
        return deform_conv2d(
            input_tensor,
            offset,
            self.weight,
            self.bias,
            stride=self.stride,
            padding=self.padding,
            dilation=self.dilation,
            mask=torch.sigmoid(mask),
        )


__all__ = ["ModulatedDeformConvPack"]
