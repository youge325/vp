"""算法基础接口 — 策略模式。"""

from abc import ABC, abstractmethod
from typing import Any


class IAlgorithm(ABC):
    """所有处理算法的抽象基类。"""

    @abstractmethod
    def process_frame(self, frame: Any, **kwargs) -> Any:
        """处理单帧。输入/输出类型取决于 Tensor 后端。"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """返回算法名称。"""
        pass

    # ------------------------------------------------------------------
    # 帧对处理接口（补帧算法需要实现）
    # ------------------------------------------------------------------

    def needs_frame_pairs(self) -> bool:
        """
        是否需要帧对处理模式。

        返回 True 表示该算法需要输入相邻两帧来生成中间帧，
        流式处理器将切换为帧对插值模式。
        默认返回 False（逐帧处理）。
        """
        return False

    def process_frame_pair(self, frame0: Any, frame1: Any, timestep: float = 0.5, **kwargs) -> Any:
        """
        处理帧对，生成指定时间步的中间帧。

        参数:
            frame0: 前一帧 Tensor
            frame1: 后一帧 Tensor
            timestep: 插值时间步 (0.0=frame0, 1.0=frame1)

        返回:
            中间帧 Tensor

        注意:
            仅当 needs_frame_pairs() 返回 True 时会被调用。
            默认实现抛出 NotImplementedError。
        """
        raise NotImplementedError(
            f"算法 '{self.get_name()}' 未实现 process_frame_pair()。"
            f"如果 needs_frame_pairs() 返回 True，必须实现此方法。"
        )

    def get_interpolation_multi(self) -> int:
        """
        返回补帧倍率（默认 2x）。

        倍率含义：2x = 每对帧生成 1 个中间帧，4x = 每对帧生成 3 个中间帧。
        """
        return 2

    # ------------------------------------------------------------------
    # 帧序列处理接口（视频超分算法需要实现）
    # ------------------------------------------------------------------

    def needs_frame_sequence(self) -> bool:
        """是否需要整段或多帧序列处理模式。"""
        return False

    def process_frame_sequence(self, frames: list[Any], **kwargs) -> list[Any]:
        """处理帧序列，默认逐帧调用 ``process_frame``。"""
        return [self.process_frame(frame, **kwargs) for frame in frames]
