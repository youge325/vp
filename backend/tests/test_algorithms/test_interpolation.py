"""补帧算法测试 — 基于 RIFE v4.25。"""

import pytest
import app.processing  # noqa: F401  # importing the package registers default algorithms
from app.algorithms.factory import AlgorithmFactory


class TestFrameInterpolationAlgorithm:
    """测试视频补帧算法。"""

    def test_is_registered(self):
        types = AlgorithmFactory.get_available_types()
        assert "frame_interpolation" in types

    def test_create_instance(self):
        try:
            algo = AlgorithmFactory.create(
                "frame_interpolation",
                tensor_backend_name="pytorch",
                multi=2,
                model_version="4.25",
            )
            assert "RIFE" in algo.get_name()
            assert "2x" in algo.get_name()
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_needs_frame_pairs(self):
        """补帧算法应返回 needs_frame_pairs()=True。"""
        try:
            algo = AlgorithmFactory.create("frame_interpolation", tensor_backend_name="pytorch")
            assert algo.needs_frame_pairs() is True
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_get_interpolation_multi(self):
        """补帧倍率应正确返回。"""
        try:
            algo = AlgorithmFactory.create(
                "frame_interpolation",
                tensor_backend_name="pytorch",
                multi=4,
            )
            assert algo.get_interpolation_multi() == 4
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_validate(self):
        try:
            algo = AlgorithmFactory.create("frame_interpolation", tensor_backend_name="pytorch")
            assert algo.validate() is True
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_process_frame_returns_input(self):
        """单帧处理模式应直接返回输入帧。"""
        try:
            import torch

            algo = AlgorithmFactory.create("frame_interpolation", tensor_backend_name="pytorch")
            frame = torch.rand(1, 3, 64, 64)
            result = algo.process_frame(frame)
            assert result is frame
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_get_description(self):
        """描述信息应包含 RIFE 和倍率。"""
        try:
            algo = AlgorithmFactory.create(
                "frame_interpolation",
                tensor_backend_name="pytorch",
                multi=4,
            )
            desc = algo.get_description()
            assert "RIFE" in desc
            assert "4x" in desc
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")


class TestSuperResolutionAlgorithm:
    """测试超分辨率占位算法。"""

    def test_is_registered(self):
        types = AlgorithmFactory.get_available_types()
        assert "super_resolution" in types

    def test_needs_frame_pairs_default(self):
        """非补帧算法默认不需要帧对处理。"""
        try:
            algo = AlgorithmFactory.create("super_resolution", tensor_backend_name="pytorch")
            assert algo.needs_frame_pairs() is False
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")


class TestAnimeOptimizationAlgorithm:
    """测试动漫帧优化占位算法。"""

    def test_is_registered(self):
        types = AlgorithmFactory.get_available_types()
        assert "anime_optimization" in types

    def test_needs_frame_pairs_default(self):
        """非补帧算法默认不需要帧对处理。"""
        try:
            algo = AlgorithmFactory.create("anime_optimization", tensor_backend_name="pytorch")
            assert algo.needs_frame_pairs() is False
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")
