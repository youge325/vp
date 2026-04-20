"""超分辨率算法占位实现。"""

from typing import Any

from app.algorithms.base import IAlgorithm
from app.algorithms.tensor_backend import ITensorBackend


class SuperResolutionAlgorithm(IAlgorithm):
    """
    超分辨率算法占位实现。

    当前为无操作实现：接收 Tensor 后原样返回。
    未来实现将：
    - 使用 SR 模型（Real-ESRGAN 等）提升帧分辨率
    - 支持可配置的放大倍率（2x, 4x）
    - 支持至少 5 种不同的超分算法
    """

    def __init__(self, tensor_backend: ITensorBackend = None, **kwargs):
        self._tensor_backend = tensor_backend
        self._scale_factor = kwargs.get("scale_factor", 2.0)
        self._algorithm_name = kwargs.get("sr_algorithm", "placeholder")

    def process_frame(self, frame: Any, **kwargs) -> Any:
        """占位实现：直接返回帧 Tensor，不做任何处理。"""
        return frame

    def process_frame_batch(self, frames: list[Any], **kwargs) -> list[Any]:
        """占位实现：直接返回所有帧 Tensor，不做任何处理。"""
        return frames

    def get_name(self) -> str:
        return "超分辨率算法(占位)"

    def validate(self) -> bool:
        """占位算法始终有效。"""
        return True

    def get_description(self) -> str:
        return (
            "视频超分辨率处理占位算法。当前实现：帧→Tensor→帧往返转换，"
            "不做实际超分处理。未来将集成Real-ESRGAN等至少5种超分算法。"
        )
