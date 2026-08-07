"""ONNX Runtime Tensor 后端实现测试。"""

import numpy as np
import pytest

from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from tests.support.tensor_backends import assert_backend_contract, module_available, require_module


class TestOnnxBackend:
    """测试 ONNX Runtime Tensor 后端。"""

    @pytest.fixture
    def backend(self):
        require_module("onnxruntime", "onnxruntime")
        return get_tensor_backend("onnx")

    def test_contract(self, backend):
        assert_backend_contract(
            backend,
            expected_dtype=np.float32,
            check_float_range=True,
        )


class TestOnnxBackendUnavailable:
    """测试 onnxruntime 未安装时的行为。"""

    def test_not_available(self):
        if module_available("onnxruntime"):
            pytest.skip("onnxruntime 已安装，跳过不可用场景测试")
        with pytest.raises(RuntimeError, match="不可用"):
            get_tensor_backend("onnx")


class TestGetTensorBackendOnnx:
    """测试 get_tensor_backend 工厂函数的 ONNX 分支。"""

    def test_get_onnx(self):
        require_module("onnxruntime", "onnxruntime")
        backend = get_tensor_backend("onnx")
        assert isinstance(backend, ITensorBackend)
