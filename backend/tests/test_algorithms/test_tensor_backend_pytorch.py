"""PyTorch Tensor 后端实现测试。"""

import pytest

pytestmark = pytest.mark.pytorch

from app.algorithms.tensor_backend import PyTorchBackend, get_tensor_backend
from tests.support.tensor_backends import assert_backend_contract, require_module


class TestPyTorchBackend:
    """测试 PyTorch Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        require_module("torch", "PyTorch")
        return PyTorchBackend()

    def test_contract(self, backend):
        assert_backend_contract(backend, expected_name="pytorch", check_float_range=True)


class TestGetTensorBackendPyTorch:
    """测试 get_tensor_backend 工厂函数的 PyTorch 分支。"""

    def test_get_pytorch(self):
        require_module("torch", "PyTorch")
        backend = get_tensor_backend("pytorch")
        assert backend.get_name() == "pytorch"

    def test_case_insensitive(self):
        require_module("torch", "PyTorch")
        backend = get_tensor_backend("PyTorch")
        assert backend.get_name() == "pytorch"
