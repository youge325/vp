"""算法工厂 — 根据任务类型创建算法实例。

``create`` 在注册表为空时抛出 ``ProcessError(INVALID_CONFIG)``,把
"忘记调用 ``register_default_algorithms``" 这种启动顺序错误从一个
晦涩的 ``ValueError`` 升级为带 TaskErrorCode 的强类型异常。
"""

from typing import Optional

from app.algorithms.base import IAlgorithm
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend
from app.errors import TaskErrorCode, raise_error


class AlgorithmFactory:
    """算法实例工厂(工厂模式)。"""

    _registry: dict[str, type[IAlgorithm]] = {}

    @classmethod
    def register(cls, algorithm_type: str, algorithm_class: type[IAlgorithm]):
        """注册算法类到指定类型。"""
        cls._registry[algorithm_type] = algorithm_class

    @classmethod
    def create(
        cls,
        algorithm_type: str,
        tensor_backend: Optional[ITensorBackend] = None,
        tensor_backend_name: str = "pytorch",
        **kwargs,
    ) -> IAlgorithm:
        """根据类型创建算法实例。

        参数:
            algorithm_type: 算法类型(如 'frame_interpolation')
            tensor_backend: 可选的预创建 Tensor 后端
            tensor_backend_name: 未提供 tensor_backend 时创建的后端名称
            **kwargs: 其他算法参数(如 multi / model_version / scale 等)
        """
        if not cls._registry:
            # Phase D.6.1 — 早失败。注册表为空意味着 ``register_default_algorithms``
            # 没有被调用过,这通常是启动顺序 bug(例如绕开 CLI 直接 import
            # 子模块的脚本)。给一个清晰的 TaskErrorCode 比 ValueError 更利于
            # 排查。
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                "Algorithm registry is empty; call register_default_algorithms() first.",
                details={"algorithm_type": algorithm_type},
            )

        if algorithm_type not in cls._registry:
            raise ValueError(f"未知算法类型: {algorithm_type}. 可用类型: {list(cls._registry.keys())}")

        if tensor_backend is None:
            tensor_backend = get_tensor_backend(tensor_backend_name)

        algorithm_class = cls._registry[algorithm_type]
        return algorithm_class(tensor_backend=tensor_backend, **kwargs)

    @classmethod
    def get_available_types(cls) -> list[str]:
        """返回已注册的算法类型列表。"""
        return list(cls._registry.keys())
