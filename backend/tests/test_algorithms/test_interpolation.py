"""补帧算法测试 — 基于 RIFE v4.25。"""

import pytest

from app.algorithms.interfaces import FramePairAlgorithm
from app.algorithms.rife_interpolation import FrameInterpolationAlgorithm
from app.algorithms.tensor_backend import get_tensor_backend
from app.planning.processing_steps import ProcessingStep

pytestmark = pytest.mark.pytorch


def _create_interpolation(**kwargs):
    parameters = {
        "backend_name": "pytorch",
        "model_version": "4.25",
        "scale": 1.0,
        "fp16": False,
        "onnx_model": None,
        "engine": "cuda",
        "model_dir": "D:/models",
        **kwargs,
    }
    get_tensor_backend("pytorch")
    return FrameInterpolationAlgorithm(**parameters)


class TestFrameInterpolationAlgorithm:
    """测试视频补帧算法。"""

    def test_create_instance(self):
        try:
            algo = _create_interpolation(model_version="4.25")
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
        with pytest.raises(ValueError, match="does not support"):
            FrameInterpolationAlgorithm(
                backend_name="paddle",
                model_version="4.25",
                scale=1.0,
                fp16=False,
                onnx_model=None,
                engine="cuda",
                model_dir="D:/models",
            )
