"""算法工厂 — 根据任务类型创建算法实例。"""

from typing import Optional
from app.algorithms.base import IAlgorithm
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend


class AlgorithmFactory:
    """算法实例工厂（工厂模式）。"""

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
        """
        根据类型创建算法实例。

        参数:
            algorithm_type: 算法类型（如 'frame_interpolation'）
            tensor_backend: 可选的预创建 Tensor 后端
            tensor_backend_name: 未提供 tensor_backend 时创建的后端名称
            **kwargs: 其他算法参数
                - multi: 补帧倍率（补帧算法专用）
                - model_version: RIFE 模型版本（补帧算法专用）
                - scale: 处理分辨率缩放（补帧算法专用）
                - fp16: 是否使用半精度推理（补帧算法专用）
                - device: 推理设备
                - model_dir: 模型权重目录
        """
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

    @classmethod
    def get_available_algorithms(cls) -> dict[str, str]:
        """返回算法类型到名称的映射。"""
        return {type_name: cls._registry[type_name]().get_name() for type_name in cls._registry}
