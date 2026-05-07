"""PyTorch Tensor 后端实现测试。"""

import pytest
import numpy as np

pytestmark = pytest.mark.pytorch

from app.algorithms.tensor_backend import PyTorchBackend, get_tensor_backend


def _is_pytorch_available():
    try:
        import torch

        return True
    except ImportError:
        return False


class TestPyTorchBackend:
    """测试 PyTorch Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        if not _is_pytorch_available():
            pytest.skip("PyTorch 未安装")
        return PyTorchBackend()

    def test_is_available(self, backend):
        assert backend.is_available() is True

    def test_get_name(self, backend):
        assert backend.get_name() == "pytorch"

    def test_numpy_to_tensor_shape(self, backend):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        tensor = backend.numpy_to_tensor(frame)
        assert tensor.shape[0] == 1
        assert tensor.shape[1] == 3
        assert tensor.shape[2] == 480
        assert tensor.shape[3] == 640

    def test_tensor_to_numpy_shape(self, backend):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        tensor = backend.numpy_to_tensor(frame)
        result = backend.tensor_to_numpy(tensor)
        assert result.shape == (480, 640, 3)
        assert result.dtype == np.uint8

    def test_roundtrip_preserves_content(self, backend):
        frame = np.random.randint(0, 255, (120, 160, 3), dtype=np.uint8)
        tensor = backend.numpy_to_tensor(frame)
        result = backend.tensor_to_numpy(tensor)
        np.testing.assert_array_almost_equal(frame, result, decimal=0)

    def test_float_range(self, backend):
        frame = np.full((10, 10, 3), 128, dtype=np.uint8)
        tensor = backend.numpy_to_tensor(frame)
        assert tensor.min() >= 0.0
        assert tensor.max() <= 1.0


class TestGetTensorBackendPyTorch:
    """测试 get_tensor_backend 工厂函数的 PyTorch 分支。"""

    def test_get_pytorch(self):
        if not _is_pytorch_available():
            pytest.skip("PyTorch 未安装")
        backend = get_tensor_backend("pytorch")
        assert backend.get_name() == "pytorch"

    def test_case_insensitive(self):
        if not _is_pytorch_available():
            pytest.skip("PyTorch 未安装")
        backend = get_tensor_backend("PyTorch")
        assert backend.get_name() == "pytorch"
