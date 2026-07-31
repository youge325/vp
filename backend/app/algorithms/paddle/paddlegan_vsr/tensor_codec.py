"""PaddleGAN RGB frame and tensor boundary conversions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def frames_to_tensor(frames: Sequence[np.ndarray], paddle: Any) -> Any:
    """Convert RGB uint8 frames to one normalized ``N,T,C,H,W`` tensor."""
    array = np.stack([np.asarray(frame, dtype=np.float32) / 255.0 for frame in frames], axis=0)
    array = np.transpose(array, (0, 3, 1, 2)).astype("float32", copy=False)
    return paddle.to_tensor(np.expand_dims(array, axis=0))


def sequence_tensor_to_frames(tensor: Any) -> list[np.ndarray]:
    """Decode a recurrent model's ``N,T,C,H,W`` output."""
    return _tensor_output_to_frames(
        tensor,
        expected_ndim=5,
        description="PaddleGAN recurrent VSR output",
        batch_index=0,
    )


def image_tensor_to_frames(tensor: Any) -> list[np.ndarray]:
    """Decode a window model's ``N,C,H,W`` output."""
    return _tensor_output_to_frames(
        tensor,
        expected_ndim=4,
        description="PaddleGAN EDVR output",
    )


def as_numpy(value: Any) -> np.ndarray:
    """Return an ndarray without importing or depending on Paddle types."""
    if isinstance(value, np.ndarray):
        return value
    numpy_fn = getattr(value, "numpy", None)
    if callable(numpy_fn):
        return numpy_fn()
    return np.asarray(value)


def shape_list(value: Any) -> list[int] | None:
    """Project a tensor-like shape onto JSON-safe integers."""
    shape = getattr(value, "shape", None)
    if shape is None:
        return None
    return [int(dim) for dim in shape]


def _tensor_output_to_frames(
    tensor: Any,
    *,
    expected_ndim: int,
    description: str,
    batch_index: int | None = None,
) -> list[np.ndarray]:
    array = as_numpy(tensor)
    if array.ndim != expected_ndim:
        raise RuntimeError(f"{description} must be {expected_ndim}D, got shape {array.shape}.")
    chw_batch = array if batch_index is None else array[batch_index]
    return [_chw_float_to_rgb_uint8(chw) for chw in chw_batch]


def _chw_float_to_rgb_uint8(chw: np.ndarray) -> np.ndarray:
    image = (np.clip(chw, 0.0, 1.0) * 255.0).round().astype(np.uint8)
    return np.transpose(image, (1, 2, 0))


__all__ = [
    "as_numpy",
    "frames_to_tensor",
    "image_tensor_to_frames",
    "sequence_tensor_to_frames",
    "shape_list",
]
