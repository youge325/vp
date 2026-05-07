"""PaddlePaddle Tensor 后端实现测试。"""

import pytest
import numpy as np

pytestmark = pytest.mark.paddle

from app.algorithms.tensor_backend import PaddleBackend, get_tensor_backend


def _is_paddle_available():
    try:
        import paddle

        return True
    except ImportError:
        return False


class TestPaddleBackend:
    """测试 PaddlePaddle Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        if not _is_paddle_available():
            pytest.skip("PaddlePaddle 未安装")
        return PaddleBackend()

    def test_is_available(self, backend):
        assert backend.is_available() is True

    def test_get_name(self):
        backend = PaddleBackend()
        assert backend.get_name() == "paddle"

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


class TestPaddleBackendUnavailable:
    """测试 PaddlePaddle 未安装时的行为。"""

    def test_not_available(self):
        if _is_paddle_available():
            pytest.skip("PaddlePaddle 已安装，跳过不可用场景测试")
        backend = PaddleBackend()
        assert backend.is_available() is False


class TestGetTensorBackendPaddle:
    """测试 get_tensor_backend 工厂函数的 Paddle 分支。"""

    def test_get_paddle(self):
        if not _is_paddle_available():
            pytest.skip("PaddlePaddle 未安装")
        backend = get_tensor_backend("paddle")
        assert backend.get_name() == "paddle"
