"""Processing pipeline package.

Importing this package as a side effect registers all default algorithm
classes with ``AlgorithmFactory``, so callers do not need to wire concrete
algorithm classes themselves.

Phase C.1.5:registration is now also reachable via an explicit call
from ``cli/main.py`` to make the startup sequence visible at one place.
The module-import side effect remains for backward compatibility with
tests that ``import app.processing.*`` without going through the CLI.
"""

from app.algorithms.factory import AlgorithmFactory
from app.processing.anime_optimization import AnimeOptimizationAlgorithm
from app.processing.frame_filters import FrameFilterChainAlgorithm
from app.processing.interpolation import FrameInterpolationAlgorithm
from app.processing.super_resolution import SuperResolutionAlgorithm


def register_default_algorithms() -> None:
    """Register all default algorithm classes with the factory.

    Idempotent by construction — ``AlgorithmFactory.register`` is a dict
    assignment, so calling this twice produces the same final registry.
    Tests that clear ``AlgorithmFactory._registry`` can call this again
    to repopulate it.
    """
    AlgorithmFactory.register("frame_interpolation", FrameInterpolationAlgorithm)
    AlgorithmFactory.register("super_resolution", SuperResolutionAlgorithm)
    AlgorithmFactory.register("anime_optimization", AnimeOptimizationAlgorithm)
    AlgorithmFactory.register("frame_filter_chain", FrameFilterChainAlgorithm)


# 模块 import 时副作用:保持向后兼容,让既有 ``import app.processing.streaming``
# 这种用法不需要先手动调 register。Phase C.1.5 的清晰化体现在 ``cli/main.py``
# 增加了显式调用,使 CLI 启动流程一眼可见。
register_default_algorithms()
