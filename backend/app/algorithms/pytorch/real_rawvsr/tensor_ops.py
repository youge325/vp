"""Tensor operations shared by Real-RawVSR optical-flow networks."""

from __future__ import annotations

import torch
from torch.nn import functional as F


def flow_warp(
    value: torch.Tensor,
    flow: torch.Tensor,
    *,
    padding_mode: str = "zeros",
) -> torch.Tensor:
    if value.shape[-2:] != flow.shape[1:3]:
        raise ValueError("Optical flow and feature spatial dimensions do not match.")
    height, width = value.shape[-2:]
    grid_y, grid_x = torch.meshgrid(
        torch.arange(height, device=value.device),
        torch.arange(width, device=value.device),
        indexing="ij",
    )
    displaced = torch.stack((grid_x, grid_y), dim=2).to(dtype=value.dtype) + flow
    normalized_x = 2.0 * displaced[..., 0] / max(width - 1, 1) - 1.0
    normalized_y = 2.0 * displaced[..., 1] / max(height - 1, 1) - 1.0
    return F.grid_sample(
        value,
        torch.stack((normalized_x, normalized_y), dim=3),
        mode="bilinear",
        padding_mode=padding_mode,
        align_corners=True,
    )


__all__ = ["flow_warp"]
