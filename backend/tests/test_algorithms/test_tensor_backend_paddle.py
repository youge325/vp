"""PaddlePaddle Tensor 后端实现测试。"""

import pytest

pytestmark = pytest.mark.paddle

from app.algorithms.tensor_backend import PaddleBackend, get_tensor_backend
from tests.support.tensor_backends import assert_backend_contract, module_available, require_module


class TestPaddleBackend:
    """测试 PaddlePaddle Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        require_module("paddle", "PaddlePaddle")
        return PaddleBackend()

    def test_contract(self, backend):
        assert_backend_contract(backend, expected_name="paddle")


class TestPaddleBackendUnavailable:
    """测试 PaddlePaddle 未安装时的行为。"""

    def test_not_available(self):
        if module_available("paddle"):
            pytest.skip("PaddlePaddle 已安装，跳过不可用场景测试")
        backend = PaddleBackend()
        assert backend.is_available() is False


class TestGetTensorBackendPaddle:
    """测试 get_tensor_backend 工厂函数的 Paddle 分支。"""

    def test_get_paddle(self):
        require_module("paddle", "PaddlePaddle")
        backend = get_tensor_backend("paddle")
        assert backend.get_name() == "paddle"
