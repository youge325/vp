"""Transfer timing tests for ``FramePayload`` lazy conversions."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.processing.streaming.frame_payload import FramePayload
from app.processing.streaming.metrics import PipelineMetrics


class _Backend:
    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, Any]:
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, Any]) -> np.ndarray:
        return tensor["tensor"].copy()

    def get_name(self) -> str:
        return "timed"


def test_ensure_tensor_records_h2d_transfer_duration() -> None:
    metrics = PipelineMetrics()
    payload = FramePayload.from_numpy(np.full((1, 1, 3), 7, dtype=np.uint8))

    payload.ensure_tensor(_Backend(), metrics)

    snapshot = metrics.snapshot()
    assert snapshot["transferCounts"] == {"h2d": 1, "d2h": 0}
    assert snapshot["transferDurationsSeconds"]["h2d"] >= 0.0
    assert snapshot["transferDurationsSeconds"]["d2h"] == 0.0


def test_ensure_numpy_records_d2h_transfer_duration() -> None:
    backend = _Backend()
    metrics = PipelineMetrics()
    payload = FramePayload.from_tensor({"tensor": np.full((1, 1, 3), 9, dtype=np.uint8)}, backend)

    payload.ensure_numpy(metrics)

    snapshot = metrics.snapshot()
    assert snapshot["transferCounts"] == {"h2d": 0, "d2h": 1}
    assert snapshot["transferDurationsSeconds"]["h2d"] == 0.0
    assert snapshot["transferDurationsSeconds"]["d2h"] >= 0.0
