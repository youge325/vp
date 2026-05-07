"""Processing pipeline package.

Importing this package as a side effect registers all default algorithm
classes with ``AlgorithmFactory``, so callers do not need to wire concrete
algorithm classes themselves.
"""

from app.algorithms.factory import AlgorithmFactory
from app.processing.anime_optimization import AnimeOptimizationAlgorithm
from app.processing.frame_filters import FrameFilterChainAlgorithm
from app.processing.interpolation import FrameInterpolationAlgorithm
from app.processing.super_resolution import SuperResolutionAlgorithm


def register_default_algorithms() -> None:
    """Register all default algorithm classes with the factory.

    Called once at package import time below; tests can invoke it again
    after clearing the factory's registry.
    """
    AlgorithmFactory.register("frame_interpolation", FrameInterpolationAlgorithm)
    AlgorithmFactory.register("super_resolution", SuperResolutionAlgorithm)
    AlgorithmFactory.register("anime_optimization", AnimeOptimizationAlgorithm)
    AlgorithmFactory.register("frame_filter_chain", FrameFilterChainAlgorithm)


register_default_algorithms()
