"""Minimal inference-only EDVR network for Real-RawVSR RGB checkpoints."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

from app.algorithms.pytorch.real_rawvsr.dcn import ModulatedDeformConvPack


class _ResidualBlockNoBatchNorm(nn.Module):
    def __init__(self, channels: int = 64) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.conv2 = nn.Conv2d(channels, channels, 3, 1, 1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return value + self.conv2(F.relu(self.conv1(value), inplace=True))


def _residual_stack(channels: int, count: int) -> nn.Sequential:
    return nn.Sequential(*(_ResidualBlockNoBatchNorm(channels) for _ in range(count)))


class _PyramidCascadingAlignment(nn.Module):
    def __init__(self, channels: int = 64, deformable_groups: int = 8) -> None:
        super().__init__()
        self.L3_offset_conv1 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.L3_offset_conv2 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.L3_dcnpack = ModulatedDeformConvPack(
            channels,
            channels,
            3,
            padding=1,
            deformable_groups=deformable_groups,
            extra_offset_mask=True,
        )
        self.L2_offset_conv1 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.L2_offset_conv2 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.L2_offset_conv3 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.L2_dcnpack = ModulatedDeformConvPack(
            channels,
            channels,
            3,
            padding=1,
            deformable_groups=deformable_groups,
            extra_offset_mask=True,
        )
        self.L2_fea_conv = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.L1_offset_conv1 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.L1_offset_conv2 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.L1_offset_conv3 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.L1_dcnpack = ModulatedDeformConvPack(
            channels,
            channels,
            3,
            padding=1,
            deformable_groups=deformable_groups,
            extra_offset_mask=True,
        )
        self.L1_fea_conv = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.cas_offset_conv1 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.cas_offset_conv2 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.cas_dcnpack = ModulatedDeformConvPack(
            channels,
            channels,
            3,
            padding=1,
            deformable_groups=deformable_groups,
            extra_offset_mask=True,
        )
        self.lrelu = nn.LeakyReLU(negative_slope=0.1, inplace=True)

    def forward(
        self,
        neighbor: list[torch.Tensor],
        reference: list[torch.Tensor],
    ) -> torch.Tensor:
        offset_l3 = self.lrelu(self.L3_offset_conv1(torch.cat((neighbor[2], reference[2]), dim=1)))
        offset_l3 = self.lrelu(self.L3_offset_conv2(offset_l3))
        feature_l3 = self.lrelu(self.L3_dcnpack((neighbor[2], offset_l3)))

        offset_l2 = self.lrelu(self.L2_offset_conv1(torch.cat((neighbor[1], reference[1]), dim=1)))
        offset_l3_up = F.interpolate(offset_l3, size=offset_l2.shape[-2:], mode="bilinear", align_corners=False)
        offset_l2 = self.lrelu(self.L2_offset_conv2(torch.cat((offset_l2, offset_l3_up * 2), dim=1)))
        offset_l2 = self.lrelu(self.L2_offset_conv3(offset_l2))
        feature_l2 = self.L2_dcnpack((neighbor[1], offset_l2))
        feature_l3 = F.interpolate(feature_l3, size=feature_l2.shape[-2:], mode="bilinear", align_corners=False)
        feature_l2 = self.lrelu(self.L2_fea_conv(torch.cat((feature_l2, feature_l3), dim=1)))

        offset_l1 = self.lrelu(self.L1_offset_conv1(torch.cat((neighbor[0], reference[0]), dim=1)))
        offset_l2_up = F.interpolate(offset_l2, size=offset_l1.shape[-2:], mode="bilinear", align_corners=False)
        offset_l1 = self.lrelu(self.L1_offset_conv2(torch.cat((offset_l1, offset_l2_up * 2), dim=1)))
        offset_l1 = self.lrelu(self.L1_offset_conv3(offset_l1))
        feature_l1 = self.L1_dcnpack((neighbor[0], offset_l1))
        feature_l2 = F.interpolate(feature_l2, size=feature_l1.shape[-2:], mode="bilinear", align_corners=False)
        feature_l1 = self.L1_fea_conv(torch.cat((feature_l1, feature_l2), dim=1))

        offset = self.lrelu(self.cas_offset_conv1(torch.cat((feature_l1, reference[0]), dim=1)))
        offset = self.lrelu(self.cas_offset_conv2(offset))
        return self.lrelu(self.cas_dcnpack((feature_l1, offset)))


class _TemporalSpatialAttentionFusion(nn.Module):
    def __init__(self, channels: int = 64, frames: int = 5, center: int = 2) -> None:
        super().__init__()
        self.center = center
        self.tAtt_1 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.tAtt_2 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.fea_fusion = nn.Conv2d(frames * channels, channels, 1)
        self.sAtt_1 = nn.Conv2d(frames * channels, channels, 1)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.avgpool = nn.AvgPool2d(3, stride=2, padding=1)
        self.sAtt_2 = nn.Conv2d(channels * 2, channels, 1)
        self.sAtt_3 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.sAtt_4 = nn.Conv2d(channels, channels, 1)
        self.sAtt_5 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.sAtt_L1 = nn.Conv2d(channels, channels, 1)
        self.sAtt_L2 = nn.Conv2d(channels * 2, channels, 3, 1, 1)
        self.sAtt_L3 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.sAtt_add_1 = nn.Conv2d(channels, channels, 1)
        self.sAtt_add_2 = nn.Conv2d(channels, channels, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.1, inplace=True)

    def forward(self, aligned: torch.Tensor) -> torch.Tensor:
        batch, frames, channels, height, width = aligned.shape
        reference = self.tAtt_2(aligned[:, self.center])
        embeddings = self.tAtt_1(aligned.reshape(-1, channels, height, width)).view(
            batch, frames, channels, height, width
        )
        correlations = torch.cat(
            tuple(torch.sum(embeddings[:, index] * reference, dim=1, keepdim=True) for index in range(frames)),
            dim=1,
        )
        weights = torch.sigmoid(correlations).unsqueeze(2).expand(-1, -1, channels, -1, -1)
        flattened = (aligned * weights).reshape(batch, frames * channels, height, width)
        feature = self.lrelu(self.fea_fusion(flattened))

        attention = self.lrelu(self.sAtt_1(flattened))
        pooled = self.lrelu(self.sAtt_2(torch.cat((self.maxpool(attention), self.avgpool(attention)), dim=1)))
        pyramid = self.lrelu(self.sAtt_L1(pooled))
        pyramid = self.lrelu(self.sAtt_L2(torch.cat((self.maxpool(pyramid), self.avgpool(pyramid)), dim=1)))
        pyramid = self.lrelu(self.sAtt_L3(pyramid))
        pyramid = F.interpolate(pyramid, size=pooled.shape[-2:], mode="bilinear", align_corners=False)
        attention = self.lrelu(self.sAtt_3(pooled)) + pyramid
        attention = self.lrelu(self.sAtt_4(attention))
        attention = F.interpolate(attention, size=(height, width), mode="bilinear", align_corners=False)
        attention = self.sAtt_5(attention)
        addition = self.sAtt_add_2(self.lrelu(self.sAtt_add_1(attention)))
        return feature * torch.sigmoid(attention) * 2 + addition


class _EdvrNet(nn.Module):
    def __init__(self, *, scale: int, channels: int = 64, frames: int = 5) -> None:
        super().__init__()
        if scale not in {2, 3, 4}:
            raise ValueError(f"EDVR scale must be 2, 3, or 4; got {scale}.")
        self.center = frames // 2
        self.scale = scale
        self.lrelu = nn.LeakyReLU(negative_slope=0.1, inplace=True)
        self.conv_first = nn.Conv2d(3, channels, 3, 1, 1)
        self.feature_extraction = _residual_stack(channels, 5)
        self.fea_L2_conv1 = nn.Conv2d(channels, channels, 3, 2, 1)
        self.fea_L2_conv2 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.fea_L3_conv1 = nn.Conv2d(channels, channels, 3, 2, 1)
        self.fea_L3_conv2 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.pcd_align = _PyramidCascadingAlignment(channels)
        self.tsa_fusion = _TemporalSpatialAttentionFusion(channels, frames, self.center)
        self.recon_trunk = _residual_stack(channels, 10)
        shuffle_scale = 3 if scale == 3 else 2
        self.sr_conv1 = nn.Conv2d(channels, channels * shuffle_scale**2, 3, 1, 1)
        if scale == 4:
            self.sr_conv2 = nn.Conv2d(channels, channels * 4, 3, 1, 1)
        self.pixel_shuffle = nn.PixelShuffle(shuffle_scale)
        self.sr_conv3 = nn.Conv2d(channels, channels, 3, 1, 1)
        self.sr_conv4 = nn.Conv2d(channels, 3, 3, 1, 1)

    def forward(self, frames: torch.Tensor) -> torch.Tensor:
        batch, count, channels, height, width = frames.shape
        center = frames[:, self.center]
        level1 = self.feature_extraction(self.lrelu(self.conv_first(frames.reshape(-1, channels, height, width))))
        level2 = self.lrelu(self.fea_L2_conv2(self.lrelu(self.fea_L2_conv1(level1))))
        level3 = self.lrelu(self.fea_L3_conv2(self.lrelu(self.fea_L3_conv1(level2))))
        level1 = level1.view(batch, count, -1, height, width)
        level2 = level2.view(batch, count, -1, level2.shape[-2], level2.shape[-1])
        level3 = level3.view(batch, count, -1, level3.shape[-2], level3.shape[-1])
        reference = [level1[:, self.center], level2[:, self.center], level3[:, self.center]]
        aligned = torch.stack(
            tuple(
                self.pcd_align([level1[:, index], level2[:, index], level3[:, index]], reference)
                for index in range(count)
            ),
            dim=1,
        )
        feature = self.recon_trunk(self.tsa_fusion(aligned))
        output = self.lrelu(self.pixel_shuffle(self.sr_conv1(feature)))
        if self.scale == 4:
            output = self.lrelu(self.pixel_shuffle(self.sr_conv2(output)))
        output = self.sr_conv4(self.lrelu(self.sr_conv3(output)))
        return output + F.interpolate(center, scale_factor=self.scale, mode="bilinear", align_corners=False)


def load_edvr_model(scale: int, weight_path: str) -> tuple[Any, nn.Module]:
    from safetensors.torch import load_file

    if not torch.cuda.is_available():
        raise RuntimeError("Real-RawVSR EDVR requires an available NVIDIA CUDA device.")
    model = _EdvrNet(scale=scale)
    model.load_state_dict(load_file(weight_path, device="cpu"), strict=True)
    model.eval().to(torch.device("cuda"))
    return torch, model


__all__ = ["load_edvr_model"]
