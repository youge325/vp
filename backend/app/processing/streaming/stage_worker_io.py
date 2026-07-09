"""Rawvideo RGB frame I/O helpers for isolated stage workers."""

from __future__ import annotations

from typing import BinaryIO

import numpy as np


class RawVideoFrameError(RuntimeError):
    """Raised when a rawvideo stream cannot yield a complete RGB frame."""


def read_rgb_frame(stream: BinaryIO, *, width: int, height: int) -> np.ndarray | None:
    """Read one ``rgb24`` frame from *stream*.

    Returns ``None`` only when EOF is reached before any frame bytes are read.
    Partial frames are corrupt rawvideo and raise ``RawVideoFrameError``.
    """
    frame_bytes = width * height * 3
    chunks: list[bytes] = []
    remaining = frame_bytes
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            if not chunks:
                return None
            raise RawVideoFrameError(
                f"partial rawvideo frame: expected {frame_bytes} bytes, got {frame_bytes - remaining}."
            )
        chunks.append(chunk)
        remaining -= len(chunk)

    return np.frombuffer(b"".join(chunks), dtype=np.uint8).reshape((height, width, 3)).copy()


def write_rgb_frame(stream: BinaryIO, frame: np.ndarray, *, width: int, height: int) -> None:
    """Write one HWC ``uint8`` RGB frame to *stream*."""
    if frame.shape != (height, width, 3):
        raise RawVideoFrameError(f"Frame shape mismatch: expected {(height, width, 3)}, got {frame.shape}.")
    if frame.dtype != np.uint8:
        frame = frame.astype(np.uint8)
    stream.write(np.ascontiguousarray(frame).tobytes())


__all__ = [
    "RawVideoFrameError",
    "read_rgb_frame",
    "write_rgb_frame",
]
