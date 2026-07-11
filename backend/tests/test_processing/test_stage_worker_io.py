from __future__ import annotations

import io

import numpy as np
import pytest

from app.processing.streaming.stage_worker_io import (
    RawVideoFrameError,
    read_rgb_frame,
    write_rgb_frame,
)


def test_read_rgb_frame_returns_none_on_clean_eof() -> None:
    assert read_rgb_frame(io.BytesIO(b""), width=1, height=1) is None


def test_read_rgb_frame_rejects_partial_frame() -> None:
    with pytest.raises(RawVideoFrameError, match="partial rawvideo frame"):
        read_rgb_frame(io.BytesIO(b"\x00\x01"), width=1, height=1)


def test_write_rgb_frame_validates_shape_and_writes_contiguous_uint8_bytes() -> None:
    stream = io.BytesIO()
    frame = np.array([[[1.2, 2.8, 3.0]]], dtype=np.float32)

    write_rgb_frame(stream, frame, width=1, height=1)

    assert stream.getvalue() == np.array([[[1, 2, 3]]], dtype=np.uint8).tobytes()
    with pytest.raises(RawVideoFrameError, match="Frame shape mismatch"):
        write_rgb_frame(stream, np.zeros((1, 2, 3), dtype=np.uint8), width=1, height=1)
