"""PyTorch Tensor 后端实现测试。"""

import pytest

from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from tests.support.tensor_backends import assert_backend_contract, require_module

pytestmark = pytest.mark.pytorch


class TestPyTorchBackend:
    """测试 PyTorch Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        require_module("torch", "PyTorch")
        return get_tensor_backend("pytorch")

    def test_contract(self, backend):
        assert_backend_contract(backend, check_float_range=True)


class TestGetTensorBackendPyTorch:
    """测试 get_tensor_backend 工厂函数的 PyTorch 分支。"""

    def test_get_pytorch(self):
        require_module("torch", "PyTorch")
        backend = get_tensor_backend("pytorch")
        assert isinstance(backend, ITensorBackend)
