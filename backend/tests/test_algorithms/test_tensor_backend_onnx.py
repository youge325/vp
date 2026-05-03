"""ONNX Runtime Tensor 后端实现测试。"""

import pytest
import numpy as np

from app.algorithms.tensor_backend import OnnxBackend, get_tensor_backend


def _is_onnx_available():
    try:
        import onnxruntime

        return True
    except ImportError:
        return False


class TestOnnxBackend:
    """测试 ONNX Runtime Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        if not _is_onnx_available():
            pytest.skip("onnxruntime 未安装")
        return OnnxBackend()

    def test_is_available(self, backend):
        assert backend.is_available() is True

    def test_get_name(self, backend):
        assert backend.get_name() == "onnx"

    def test_numpy_to_tensor_shape(self, backend):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        tensor = backend.numpy_to_tensor(frame)
        assert tensor.shape == (1, 3, 480, 640)
        assert tensor.dtype == np.float32

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


class TestOnnxBackendUnavailable:
    """测试 onnxruntime 未安装时的行为。"""

    def test_not_available(self):
        if _is_onnx_available():
            pytest.skip("onnxruntime 已安装，跳过不可用场景测试")
        backend = OnnxBackend()
        assert backend.is_available() is False


class TestGetTensorBackendOnnx:
    """测试 get_tensor_backend 工厂函数的 ONNX 分支。"""

    def test_get_onnx(self):
        if not _is_onnx_available():
            pytest.skip("onnxruntime 未安装")
        backend = get_tensor_backend("onnx")
        assert backend.get_name() == "onnx"
