"""Shared RGB validation, spatial policy, CUDA projection, and output codec."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class _PreparedRgbFrames:
    frames: tuple[np.ndarray, ...]
    height: int
    width: int


@dataclass(frozen=True, slots=True)
class RgbTensorCodec:
    """Apply one model's spatial contract at the tensor boundary."""

    display_name: str
    minimum_size: int
    size_multiple: int
    scale_factor: int

    def prepare(self, frames: Sequence[Any]) -> _PreparedRgbFrames | None:
        if not frames:
            return None
        arrays = [np.asarray(frame) for frame in frames]
        if any(array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 3 for array in arrays):
            raise ValueError(f"{self.display_name} input must be HxWx3 RGB uint8 frames.")
        if any(array.shape != arrays[0].shape for array in arrays):
            raise ValueError(f"{self.display_name} requires identical RGB dimensions for every input frame.")
        height, width = arrays[0].shape[:2]
        padded_height = max(self.minimum_size, _round_up(height, self.size_multiple))
        padded_width = max(self.minimum_size, _round_up(width, self.size_multiple))
        return _PreparedRgbFrames(
            frames=tuple(_pad_spatial(frame, padded_height, padded_width) for frame in arrays),
            height=height,
            width=width,
        )

    @staticmethod
    def to_cuda(torch: Any, frames: Sequence[np.ndarray]) -> Any:
        return (
            torch.from_numpy(np.stack(frames, axis=0))
            .permute(0, 3, 1, 2)
            .unsqueeze(0)
            .to(device="cuda", dtype=torch.float32)
            / 255.0
        )

    def to_frames(self, torch: Any, output: Any, prepared: _PreparedRgbFrames) -> list[np.ndarray]:
        cropped = output[
            ...,
            : prepared.height * self.scale_factor,
            : prepared.width * self.scale_factor,
        ]
        if cropped.ndim == 4:
            cropped = cropped[0].unsqueeze(0)
        elif cropped.ndim == 5:
            cropped = cropped[0]
        else:
            raise RuntimeError(f"{self.display_name} returned an invalid tensor rank: {cropped.ndim}.")
        array = cropped.clamp(0, 1).mul(255.0).round().to(dtype=torch.uint8).permute(0, 2, 3, 1).cpu().numpy()
        return [np.ascontiguousarray(frame) for frame in array]


def _pad_spatial(frame: np.ndarray, height: int, width: int) -> np.ndarray:
    return np.pad(frame, ((0, height - frame.shape[0]), (0, width - frame.shape[1]), (0, 0)), mode="edge")


def _round_up(value: int, modulo: int) -> int:
    return ((value + modulo - 1) // modulo) * modulo


__all__ = ["RgbTensorCodec"]
