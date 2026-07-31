"""PyTorch-only tensor-path tests for FrameFilterChainAlgorithm."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.processing.frame_filters import FrameFilterChainAlgorithm

pytestmark = pytest.mark.pytorch


class _PyTorchTensorBackend:
    """A minimal backend identity used by the frame-filter tensor path."""

    def numpy_to_tensor(self, array: np.ndarray) -> np.ndarray:
        return array

    def tensor_to_numpy(self, tensor: np.ndarray) -> np.ndarray:
        return tensor

    def get_name(self) -> str:
        return "pytorch"


def _make_algorithm(filters: list[dict[str, Any]]) -> FrameFilterChainAlgorithm:
    return FrameFilterChainAlgorithm(tensor_backend=_PyTorchTensorBackend(), filters=filters)


def test_zero_denoise_keeps_tensor_identity_path():
    torch = pytest.importorskip("torch")
    tensor = torch.rand((1, 3, 8, 10), dtype=torch.float32)
    algorithm = _make_algorithm(
        [
            {"kind": "denoise", "enabled": True, "params": {"strength": 0, "colorStrength": 0}},
        ]
    )

    assert algorithm.can_process_tensor(_PyTorchTensorBackend()) is True
    assert algorithm.process_tensor(tensor, _PyTorchTensorBackend()) is tensor


def test_process_tensor_scale_crop_pad_color_preserves_tensor_contract():
    torch = pytest.importorskip("torch")
    tensor = torch.full((1, 3, 8, 10), 0.25, dtype=torch.float32)
    algorithm = _make_algorithm(
        [
            {"kind": "scale", "enabled": True, "params": {"mode": "resolution", "width": 6, "height": 4}},
            {"kind": "crop", "enabled": True, "params": {"x": 1, "y": 1, "width": 4, "height": 2}},
            {
                "kind": "pad",
                "enabled": True,
                "params": {"top": 1, "bottom": 1, "left": 2, "right": 0, "color": "#ff0000"},
            },
            {"kind": "color", "enabled": True, "params": {"brightness": 0.2, "contrast": 1.1, "saturation": 1.0}},
        ]
    )

    output = algorithm.process_tensor(tensor, _PyTorchTensorBackend())

    assert tuple(output.shape) == (1, 3, 4, 6)
    assert output.dtype == tensor.dtype
    assert output.device == tensor.device
    assert float(output.min()) >= 0.0
    assert float(output.max()) <= 1.0
    assert output[:, 0, 0, 0].item() > output[:, 1, 0, 0].item()


def test_process_tensor_rejects_unsupported_filter_without_cpu_fallback():
    torch = pytest.importorskip("torch")
    tensor = torch.full((1, 3, 8, 10), 0.25, dtype=torch.float32)
    algorithm = _make_algorithm(
        [
            {"kind": "denoise", "enabled": True, "params": {"strength": 10, "colorStrength": 10}},
        ]
    )

    with pytest.raises(RuntimeError, match="does not support tensor processing"):
        algorithm.process_tensor(tensor, _PyTorchTensorBackend())
