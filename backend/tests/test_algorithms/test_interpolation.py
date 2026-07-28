"""补帧算法测试 — 基于 RIFE v4.25。"""

from typing import cast

import pytest

pytestmark = pytest.mark.pytorch

from app.algorithms.interfaces import FramePairAlgorithm
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from app.planning import ProcessingStep
from app.processing.interpolation import FrameInterpolationAlgorithm


def _create_interpolation(**kwargs):
    return FrameInterpolationAlgorithm(tensor_backend=get_tensor_backend("pytorch"), **kwargs)


class TestFrameInterpolationAlgorithm:
    """测试视频补帧算法。"""

    def test_create_instance(self):
        try:
            algo = _create_interpolation(multi=2, model_version="4.25")
            assert isinstance(algo, FramePairAlgorithm)
        except RuntimeError:
            pytest.skip("Tensor 后端不可用")

    def test_stage_descriptor_declares_pair_mode_and_multiplier(self):
        step = ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 4},
            stage_name="01_frame_interpolation",
        )

        assert step.execution_mode == "pair"
        assert step.algorithm_kwargs["multi"] == 4

    def test_rejects_paddle_backend_instead_of_bridging_through_pytorch(self):
        class _PaddleBackend:
            @staticmethod
            def get_name():
                return "paddle"

        with pytest.raises(ValueError, match="does not support"):
            FrameInterpolationAlgorithm(tensor_backend=cast(ITensorBackend, _PaddleBackend()))
