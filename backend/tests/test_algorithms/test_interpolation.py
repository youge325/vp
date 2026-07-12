"""补帧算法测试 — 基于 RIFE v4.25。"""

import pytest

pytestmark = pytest.mark.pytorch

from app.algorithms.tensor_backend import get_tensor_backend
from app.processing.interpolation import FrameInterpolationAlgorithm
from app.processing.super_resolution import SuperResolutionAlgorithm


def _create_interpolation(**kwargs):
    return FrameInterpolationAlgorithm(tensor_backend=get_tensor_backend("pytorch"), **kwargs)


class TestFrameInterpolationAlgorithm:
    """测试视频补帧算法。"""

    def test_create_instance(self):
        try:
            algo = _create_interpolation(multi=2, model_version="4.25")
            assert "RIFE" in algo.get_name()
            assert "2x" in algo.get_name()
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_needs_frame_pairs(self):
        """补帧算法应返回 needs_frame_pairs()=True。"""
        try:
            algo = _create_interpolation()
            assert algo.needs_frame_pairs() is True
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_get_interpolation_multi(self):
        """补帧倍率应正确返回。"""
        try:
            algo = _create_interpolation(multi=4)
            assert algo.get_interpolation_multi() == 4
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_process_frame_returns_input(self):
        """单帧处理模式应直接返回输入帧。"""
        try:
            import torch

            algo = _create_interpolation()
            frame = torch.rand(1, 3, 64, 64)
            result = algo.process_frame(frame)
            assert result is frame
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")


class TestSuperResolutionAlgorithm:
    """测试超分辨率占位算法。"""

    def test_needs_frame_pairs_default(self):
        """非补帧算法默认不需要帧对处理。"""
        try:
            algo = SuperResolutionAlgorithm(tensor_backend=get_tensor_backend("pytorch"))
            assert algo.needs_frame_pairs() is False
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")
