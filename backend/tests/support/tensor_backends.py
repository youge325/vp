from __future__ import annotations

import importlib
from typing import Any

import numpy as np
import pytest


def module_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True


def require_module(module_name: str, display_name: str) -> None:
    if not module_available(module_name):
        pytest.skip(f"{display_name} 未安装")


def assert_numpy_to_tensor_shape(backend: Any, *, expected_dtype: Any = None) -> None:
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    tensor = backend.numpy_to_tensor(frame)
    assert tuple(tensor.shape) == (1, 3, 480, 640)
    if expected_dtype is not None:
        assert tensor.dtype == expected_dtype


def assert_tensor_to_numpy_shape(backend: Any) -> None:
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = backend.tensor_to_numpy(backend.numpy_to_tensor(frame))
    assert result.shape == (480, 640, 3)
    assert result.dtype == np.uint8


def assert_roundtrip_preserves_content(backend: Any) -> None:
    frame = np.random.randint(0, 255, (120, 160, 3), dtype=np.uint8)
    result = backend.tensor_to_numpy(backend.numpy_to_tensor(frame))
    np.testing.assert_array_almost_equal(frame, result, decimal=0)


def assert_float_range(backend: Any) -> None:
    tensor = backend.numpy_to_tensor(np.full((10, 10, 3), 128, dtype=np.uint8))
    assert tensor.min() >= 0.0
    assert tensor.max() <= 1.0


def assert_backend_contract(
    backend: Any,
    *,
    expected_name: str,
    expected_dtype: Any = None,
    check_float_range: bool = False,
) -> None:
    assert backend.is_available() is True
    assert backend.get_name() == expected_name
    assert_numpy_to_tensor_shape(backend, expected_dtype=expected_dtype)
    assert_tensor_to_numpy_shape(backend)
    assert_roundtrip_preserves_content(backend)
    if check_float_range:
        assert_float_range(backend)
