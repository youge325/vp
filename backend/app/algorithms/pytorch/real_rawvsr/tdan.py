"""Minimal inference-only TDAN network for Real-RawVSR RGB checkpoints."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import torch
from torch import nn

from app.algorithms.pytorch.real_rawvsr.dcn import ModulatedDeformConvPack

if TYPE_CHECKING:
    from app.algorithms.pytorch.real_rawvsr.sequence_adapter import ModelLoadSpec


class _ResidualBlock(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(64, 64, 3, 1, 1)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(64, 64, 3, 1, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return value + self.conv2(self.relu(self.conv1(value)))


class _Upsampler(nn.Sequential):
    def __init__(self, scale: int) -> None:
        modules: list[nn.Module] = []
        if scale > 0 and scale & (scale - 1) == 0:
            for _ in range(int(math.log2(scale))):
                modules.extend((nn.Conv2d(64, 256, 3, padding=1), nn.PixelShuffle(2)))
        elif scale == 3:
            modules.extend((nn.Conv2d(64, 576, 3, padding=1), nn.PixelShuffle(3)))
        else:
            raise ValueError(f"TDAN scale must be 2, 3, or 4; got {scale}.")
        super().__init__(*modules)


class _TdanNet(nn.Module):
    def __init__(self, *, scale: int, frames: int) -> None:
        super().__init__()
        self.conv_first = nn.Conv2d(3, 64, 3, padding=1)
        self.residual_layer = nn.Sequential(*(_ResidualBlock() for _ in range(5)))
        self.relu = nn.ReLU(inplace=True)
        self.cr = nn.Conv2d(128, 64, 3, padding=1)
        self.off2d_1 = nn.Conv2d(64, 64, 3, padding=1)
        self.dconv_1 = self._dcn()
        self.off2d_2 = nn.Conv2d(64, 64, 3, padding=1)
        self.deconv_2 = self._dcn()
        self.off2d_3 = nn.Conv2d(64, 64, 3, padding=1)
        self.deconv_3 = self._dcn()
        self.off2d = nn.Conv2d(64, 64, 3, padding=1)
        self.dconv = self._dcn()
        self.recon_lr = nn.Conv2d(64, 3, 3, padding=1)
        self.fea_ex = nn.Sequential(nn.Conv2d(3 * frames, 64, 3, padding=1), nn.ReLU())
        self.recon_layer = nn.Sequential(*(_ResidualBlock() for _ in range(10)))
        self.up = nn.Sequential(_Upsampler(scale), nn.Conv2d(64, 3, 3, padding=1, bias=False))

    @staticmethod
    def _dcn() -> ModulatedDeformConvPack:
        return ModulatedDeformConvPack(
            64,
            64,
            3,
            padding=1,
            deformable_groups=8,
            extra_offset_mask=True,
        )

    def _align(self, features: torch.Tensor, center_frame: torch.Tensor) -> torch.Tensor:
        count = features.shape[1]
        center = count // 2
        reference = features[:, center]
        aligned: list[torch.Tensor] = []
        for index in range(count):
            if index == center:
                aligned.append(center_frame.unsqueeze(1))
                continue
            support = features[:, index]
            feature = self.cr(torch.cat((reference, support), dim=1))
            feature = self.dconv_1((feature, self.off2d_1(feature)))
            feature = self.deconv_2((feature, self.off2d_2(feature)))
            feature = self.deconv_3((support, self.off2d_3(feature)))
            feature = self.dconv((feature, self.off2d(feature)))
            aligned.append(self.recon_lr(feature).unsqueeze(1))
        return torch.cat(aligned, dim=1)

    def forward(self, frames: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        batch, count, channels, height, width = frames.shape
        center = count // 2
        feature = self.relu(self.conv_first(frames.reshape(-1, channels, height, width)))
        feature = self.residual_layer(feature).view(batch, count, -1, height, width)
        aligned = self._align(feature, frames[:, center])
        reconstruction = self.fea_ex(aligned.reshape(batch, -1, height, width))
        return self.up(self.recon_layer(reconstruction)), aligned


def load_tdan_model(spec: ModelLoadSpec, weight_path: str) -> tuple[Any, nn.Module]:
    from safetensors.torch import load_file

    if not torch.cuda.is_available():
        raise RuntimeError("Real-RawVSR TDAN requires an available NVIDIA CUDA device.")
    model = _TdanNet(scale=spec.scale_factor, frames=spec.num_frames)
    model.load_state_dict(load_file(weight_path, device="cpu"), strict=True)
    model.eval().to(torch.device("cuda"))
    return torch, model


__all__ = ["load_tdan_model"]
