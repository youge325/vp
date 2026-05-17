"""Processing pipeline package.

Phase D.6.1 — 模块 import 时不再调用 ``register_default_algorithms``。
注册唯一的入口是 [cli/main.py](../cli/main.py) 的 ``_startup_hooks``;若
有脚本/测试绕开 CLI 直接 ``from app.processing.streaming import ...``,
``AlgorithmFactory.create`` 会因为注册表为空抛 ``INVALID_CONFIG``,提示
显式调用 ``register_default_algorithms()``。
"""

from app.algorithms.factory import AlgorithmFactory
from app.processing.anime_optimization import AnimeOptimizationAlgorithm
from app.processing.frame_filters import FrameFilterChainAlgorithm
from app.processing.interpolation import FrameInterpolationAlgorithm
from app.processing.super_resolution import SuperResolutionAlgorithm


def register_default_algorithms() -> None:
    """把全部内置算法注册进 ``AlgorithmFactory``。

    幂等:``AlgorithmFactory.register`` 是 dict 赋值,重复调用产生相同
    的最终注册表;清空注册表的测试可以再次调用此函数恢复。
    """
    AlgorithmFactory.register("frame_interpolation", FrameInterpolationAlgorithm)
    AlgorithmFactory.register("super_resolution", SuperResolutionAlgorithm)
    AlgorithmFactory.register("anime_optimization", AnimeOptimizationAlgorithm)
    AlgorithmFactory.register("frame_filter_chain", FrameFilterChainAlgorithm)
