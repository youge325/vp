"""Shared RGB frame validation, padding, and CUDA tensor projection."""

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


def _validate_rgb_frames(frames: Sequence[Any], display_name: str) -> list[np.ndarray]:
    arrays = [np.asarray(frame) for frame in frames]
    if any(array.dtype != np.uint8 or array.ndim != 3 or array.shape[2] != 3 for array in arrays):
        raise ValueError(f"{display_name} input must be HxWx3 RGB uint8 frames.")
    if arrays and any(array.shape != arrays[0].shape for array in arrays):
        raise ValueError(f"{display_name} requires identical RGB dimensions for every input frame.")
    return arrays


def _pad_spatial(frame: np.ndarray, height: int, width: int) -> np.ndarray:
    return np.pad(frame, ((0, height - frame.shape[0]), (0, width - frame.shape[1]), (0, 0)), mode="edge")


def _round_up(value: int, modulo: int) -> int:
    return ((value + modulo - 1) // modulo) * modulo


def prepare_rgb_frames(
    frames: Sequence[Any],
    display_name: str,
    *,
    minimum_size: int,
    spatial_modulo: int = 1,
) -> _PreparedRgbFrames | None:
    if not frames:
        return None
    normalized = _validate_rgb_frames(frames, display_name)
    height, width = normalized[0].shape[:2]
    padded_height = max(minimum_size, _round_up(height, spatial_modulo))
    padded_width = max(minimum_size, _round_up(width, spatial_modulo))
    return _PreparedRgbFrames(
        frames=tuple(_pad_spatial(frame, padded_height, padded_width) for frame in normalized),
        height=height,
        width=width,
    )


def frames_to_cuda_tensor(torch: Any, frames: Sequence[np.ndarray]) -> Any:
    return (
        torch.from_numpy(np.stack(frames, axis=0))
        .permute(0, 3, 1, 2)
        .unsqueeze(0)
        .to(device="cuda", dtype=torch.float32)
        / 255.0
    )


__all__ = [
    "frames_to_cuda_tensor",
    "prepare_rgb_frames",
]
