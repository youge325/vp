"""Algorithm descriptor resolution rejects missing product decisions."""

from __future__ import annotations

import pytest

from app.catalog.algorithm_capabilities import resolve_stage_descriptor
from app.catalog.stage_descriptors import ONNX_SUPER_RESOLUTION_DESCRIPTOR


def test_super_resolution_descriptor_requires_an_explicit_algorithm() -> None:
    with pytest.raises(ValueError, match="sr_algorithm"):
        resolve_stage_descriptor("super_resolution", {})


def test_dynamic_onnx_super_resolution_route_remains_supported() -> None:
    assert (
        resolve_stage_descriptor("super_resolution", {"sr_algorithm": "custom-model"})
        is ONNX_SUPER_RESOLUTION_DESCRIPTOR
    )
