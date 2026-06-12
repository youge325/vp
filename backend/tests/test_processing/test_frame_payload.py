"""Tests for lazy host/device conversion inside ``FramePayload``."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics


class _CountingBackend:
    def __init__(self, name: str = "counting") -> None:
        self.name = name
        self.to_tensor_calls = 0
        self.to_numpy_calls = 0

    def get_name(self) -> str:
        return self.name

    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, Any]:
        self.to_tensor_calls += 1
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, Any]) -> np.ndarray:
        self.to_numpy_calls += 1
        return tensor["tensor"].copy()


def test_ensure_tensor_reuses_cached_upload() -> None:
    backend = _CountingBackend()
    metrics = PipelineMetrics()
    frame = np.full((1, 1, 3), 7, dtype=np.uint8)
    payload = FramePayload.from_numpy(frame)

    first = payload.ensure_tensor(backend, metrics)
    second = payload.ensure_tensor(backend, metrics)

    assert first is second
    assert backend.to_tensor_calls == 1
    assert metrics.snapshot()["transferCounts"] == {"h2d": 1, "d2h": 0}


def test_ensure_numpy_reuses_cached_download() -> None:
    backend = _CountingBackend()
    metrics = PipelineMetrics()
    tensor = {"tensor": np.full((1, 1, 3), 9, dtype=np.uint8)}
    payload = FramePayload.from_tensor(tensor, backend)

    first = payload.ensure_numpy(metrics)
    second = payload.ensure_numpy(metrics)

    assert first is second
    assert backend.to_numpy_calls == 1
    assert metrics.snapshot()["transferCounts"] == {"h2d": 0, "d2h": 1}


def test_tensor_output_does_not_reuse_source_numpy() -> None:
    backend = _CountingBackend()
    metrics = PipelineMetrics()
    source = np.full((1, 1, 3), 1, dtype=np.uint8)
    output_tensor = {"tensor": np.full((1, 1, 3), 5, dtype=np.uint8)}

    source_payload = FramePayload.from_numpy(source)
    source_payload.ensure_tensor(backend, metrics)
    output_payload = FramePayload.from_tensor(output_tensor, backend)

    result = output_payload.ensure_numpy(metrics)

    np.testing.assert_array_equal(result, np.full((1, 1, 3), 5, dtype=np.uint8))
    assert not np.array_equal(result, source)
    assert backend.to_numpy_calls == 1


def test_backend_mismatch_fails_loudly() -> None:
    backend_a = _CountingBackend("a")
    backend_b = _CountingBackend("b")
    payload = FramePayload.from_tensor({"tensor": np.zeros((1, 1, 3), dtype=np.uint8)}, backend_a)

    with pytest.raises(RuntimeError, match="backend mismatch"):
        payload.ensure_tensor(backend_b)
