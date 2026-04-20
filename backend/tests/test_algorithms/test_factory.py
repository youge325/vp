"""算法工厂测试。"""

import pytest
from app.algorithms.base import IAlgorithm
from app.algorithms.factory import AlgorithmFactory, register_default_algorithms


class MockAlgorithm(IAlgorithm):
    """用于测试的模拟算法。"""

    def __init__(self, tensor_backend=None, **kwargs):
        self._tensor_backend = tensor_backend
        self._kwargs = kwargs

    def process_frame(self, frame, **kwargs):
        return frame

    def process_frame_batch(self, frames, **kwargs):
        return frames

    def get_name(self):
        return "MockAlgorithm"

    def validate(self):
        return True


class TestAlgorithmFactory:
    """测试 AlgorithmFactory 类。"""

    def setup_method(self):
        """每个测试前保存并清空注册表。"""
        self._saved_registry = dict(AlgorithmFactory._registry)
        AlgorithmFactory._registry = {}

    def teardown_method(self):
        """每个测试后恢复注册表。"""
        AlgorithmFactory._registry = self._saved_registry

    def test_register_and_create(self):
        AlgorithmFactory.register("mock", MockAlgorithm)
        algo = AlgorithmFactory.create("mock")
        assert isinstance(algo, MockAlgorithm)
        assert algo.get_name() == "MockAlgorithm"

    def test_create_unknown_type_raises(self):
        with pytest.raises(ValueError, match="未知算法类型"):
            AlgorithmFactory.create("nonexistent")

    def test_get_available_types(self):
        AlgorithmFactory.register("type_a", MockAlgorithm)
        AlgorithmFactory.register("type_b", MockAlgorithm)
        types = AlgorithmFactory.get_available_types()
        assert "type_a" in types
        assert "type_b" in types

    def test_register_default_algorithms(self):
        register_default_algorithms()
        types = AlgorithmFactory.get_available_types()
        assert "frame_interpolation" in types
        assert "super_resolution" in types
        assert "anime_optimization" in types

    def test_create_with_tensor_backend_name(self):
        AlgorithmFactory.register("mock", MockAlgorithm)
        algo = AlgorithmFactory.create("mock", tensor_backend_name="pytorch")
        assert algo is not None
