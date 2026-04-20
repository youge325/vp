"""管道过滤器基类和管道编排器（管道-过滤器模式）。"""

from app.utils.logger import get_logger
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = get_logger(__name__)


class Filter(ABC):
    """管道-过滤器模式中的抽象过滤器。"""

    @abstractmethod
    def process(self, data: Any, context: dict) -> Any:
        """
        处理数据并返回转换后的数据。

        参数:
            data: 输入数据（类型取决于过滤器）
            context: 过滤器间传递元数据的共享上下文字典

        返回:
            转换后的数据
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """返回过滤器名称。"""
        pass


class Pipeline:
    """
    管道编排器，将过滤器串联执行。

    数据依次流经每个过滤器：
    输入 → 过滤器1 → 过滤器2 → ... → 过滤器N → 输出
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._filters: list[Filter] = []

    def add_filter(self, filter_instance: Filter) -> "Pipeline":
        """向管道添加过滤器。返回 self 以支持链式调用。"""
        self._filters.append(filter_instance)
        logger.info(f"管道 '{self.name}': 已添加过滤器 '{filter_instance.get_name()}'")
        return self

    def execute(self, input_data: Any, context: Optional[dict] = None) -> Any:
        """
        执行管道：将数据依次通过所有过滤器。

        参数:
            input_data: 初始输入数据
            context: 共享上下文字典

        返回:
            最终输出数据
        """
        if context is None:
            context = {}

        data = input_data
        for i, filter_instance in enumerate(self._filters):
            filter_name = filter_instance.get_name()
            logger.info(f"管道 '{self.name}': 执行过滤器 [{i + 1}/{len(self._filters)}] '{filter_name}'")
            data = filter_instance.process(data, context)
            logger.info(f"管道 '{self.name}': 过滤器 '{filter_name}' 执行完成")

        return data

    def get_filter_names(self) -> list[str]:
        """返回管道中所有过滤器的名称。"""
        return [f.get_name() for f in self._filters]

    def clear_filters(self) -> None:
        """移除管道中所有过滤器。"""
        self._filters.clear()
