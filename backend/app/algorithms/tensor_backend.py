"""Tensor 后端策略 — 支持 PyTorch、PaddlePaddle 和 ONNX Runtime。"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ITensorBackend(ABC):
    """帧转换的 Tensor 后端抽象接口。"""

    @abstractmethod
    def numpy_to_tensor(self, frame: np.ndarray) -> Any:
        """将 numpy 数组 (HWC, uint8) 转换为后端 Tensor。"""
        pass

    @abstractmethod
    def tensor_to_numpy(self, tensor: Any) -> np.ndarray:
        """将后端 Tensor 转换回 numpy 数组 (HWC, uint8)。"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """返回后端名称。"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查后端是否可用。"""
        pass

    @abstractmethod
    def get_supported_devices(self) -> list[str]:
        """返回该后端支持的 GPU 设备厂商列表。"""
        pass

    @abstractmethod
    def get_supported_engines(self) -> list[str]:
        """返回该后端支持的推理引擎列表。"""
        pass


class PyTorchBackend(ITensorBackend):
    """PyTorch Tensor 后端。"""

    def __init__(self):
        self._torch = None
        try:
            import torch

            self._torch = torch
        except ImportError:
            logger.warning("PyTorch 未安装")

    def numpy_to_tensor(self, frame: np.ndarray) -> Any:
        """将 numpy (HWC, uint8) 转换为 PyTorch Tensor (1CHW, float32 [0,1])。"""
        # 参考: ECCV2022-RIFE inference_video.py 第 211-212 行
        # torch.from_numpy(np.transpose(lastframe, (2,0,1))).to(device).unsqueeze(0).float() / 255.
        tensor = self._torch.from_numpy(np.transpose(frame, (2, 0, 1)).copy()).unsqueeze(0).float() / 255.0
        if self._torch.cuda.is_available():
            tensor = tensor.cuda()
        return tensor

    def tensor_to_numpy(self, tensor: Any) -> np.ndarray:
        """将 PyTorch Tensor (1CHW, float32) 转换为 numpy (HWC, uint8)。"""
        # 参考: ECCV2022-RIFE inference_video.py 第 243 行
        # (I1[0] * 255).byte().cpu().numpy().transpose(1, 2, 0)[:h, :w]
        frame = (tensor[0] * 255.0).byte().cpu().numpy()
        frame = np.transpose(frame, (1, 2, 0))
        return frame

    def get_name(self) -> str:
        return "pytorch"

    def is_available(self) -> bool:
        return self._torch is not None

    def get_supported_devices(self) -> list[str]:
        return ["nvidia", "intel", "amd"]

    def get_supported_engines(self) -> list[str]:
        import importlib.util

        engines = []
        if self._torch is not None and self._torch.cuda.is_available():
            engines.append("cuda")
            if (
                importlib.util.find_spec("torch_tensorrt") is not None
                or importlib.util.find_spec("tensorrt") is not None
            ):
                engines.append("tensorrt")
        return engines


class PaddleBackend(ITensorBackend):
    """PaddlePaddle Tensor 后端。"""

    def __init__(self):
        self._paddle = None
        try:
            import paddle

            self._paddle = paddle
        except ImportError:
            logger.warning("PaddlePaddle 未安装")

    def numpy_to_tensor(self, frame: np.ndarray) -> Any:
        """将 numpy (HWC, uint8) 转换为 Paddle Tensor (1CHW, float32 [0,1])。"""
        # paddle.to_tensor(np.transpose(frame, (2,0,1))).unsqueeze(0).astype("float32") / 255.
        tensor = self._paddle.to_tensor(np.transpose(frame, (2, 0, 1)).copy()).unsqueeze(0).astype("float32") / 255.0
        if self._paddle.device.is_compiled_with_cuda():
            tensor = tensor.cuda()
        return tensor

    def tensor_to_numpy(self, tensor: Any) -> np.ndarray:
        """将 Paddle Tensor (1CHW, float32) 转换为 numpy (HWC, uint8)。"""
        frame = (tensor[0] * 255.0).astype("uint8").numpy()
        frame = np.transpose(frame, (1, 2, 0))
        return frame

    def get_name(self) -> str:
        return "paddle"

    def is_available(self) -> bool:
        return self._paddle is not None

    def get_supported_devices(self) -> list[str]:
        return ["nvidia", "intel", "amd", "hygon"]

    def get_supported_engines(self) -> list[str]:
        engines = []
        if self._paddle is not None:
            if self._paddle.device.is_compiled_with_cuda():
                engines.append("cuda")
            if self._paddle.device.is_compiled_with_rocm():
                engines.append("dcu")
            try:
                from paddle.inference import Config

                c = Config()
                if hasattr(c, "enable_tensorrt_engine"):
                    engines.append("tensorrt")
            except Exception:
                pass
        return engines


class OnnxBackend(ITensorBackend):
    """ONNX Runtime Tensor 后端。

    ONNX Runtime 直接接受 numpy ndarray 作为输入,因此本后端的 "tensor"
    实际上就是 numpy ndarray (1CHW, float32)。

    Phase D.6.1 — 不再在 ``__init__`` 内 ``import onnxruntime`` 或调用
    ``register_native_dll_paths``。理由:
    - CLI 入口已在 [cli/main.py](../cli/main.py) 的 ``_startup_hooks`` 显式
      注册 DLL 路径,这里再调一次属于重复 bootstrap。
    - ``onnxruntime`` 的 import 涉及 CUDA/TensorRT DLL 探测,放到首次使用
      时再触发,可让"工厂只构造 PyTorch 后端"这种典型路径不付 ORT 启动成本。

    可用性检查走 ``importlib.util.find_spec``,只看包是否存在,不真的 import。
    """

    def __init__(self):
        self._ort: Any = None

    def _get_ort(self) -> Any:
        """Lazy import onnxruntime;首次成功后缓存到 ``self._ort``。"""
        if self._ort is not None:
            return self._ort
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("onnxruntime 未安装") from exc
        self._ort = ort
        return self._ort

    def numpy_to_tensor(self, frame: np.ndarray) -> Any:
        """将 numpy (HWC, uint8) 转换为 ONNX Tensor (1CHW, float32 [0,1])。"""
        tensor = np.transpose(frame, (2, 0, 1)).astype(np.float32).copy()
        tensor = np.expand_dims(tensor, 0) / 255.0
        return tensor

    def tensor_to_numpy(self, tensor: Any) -> np.ndarray:
        """将 ONNX Tensor (1CHW, float32) 转换为 numpy (HWC, uint8)。"""
        frame = (tensor[0] * 255.0).clip(0, 255).astype(np.uint8)
        frame = np.transpose(frame, (1, 2, 0))
        return frame

    def get_name(self) -> str:
        return "onnx"

    def is_available(self) -> bool:
        """轻量探测 onnxruntime 是否安装,不触发实际 import。"""
        import importlib.util

        return importlib.util.find_spec("onnxruntime") is not None

    def get_supported_devices(self) -> list[str]:
        return ["nvidia", "intel", "amd"]

    def get_supported_engines(self) -> list[str]:
        if not self.is_available():
            return []
        try:
            ort = self._get_ort()
        except RuntimeError:
            return []
        providers = ort.get_available_providers()
        engines: list[str] = []
        if "TensorrtExecutionProvider" in providers:
            engines.append("tensorrt")
        if "CUDAExecutionProvider" in providers:
            engines.append("cuda")
        if "DmlExecutionProvider" in providers:
            engines.append("directml")
        if "ROCMExecutionProvider" in providers:
            engines.append("rocm")
        if not engines:
            engines.append("cpu")
        return engines


def get_tensor_backend(name: str) -> ITensorBackend:
    """根据名称获取 Tensor 后端的工厂函数。"""
    backends = {
        "pytorch": PyTorchBackend,
        "paddle": PaddleBackend,
        "onnx": OnnxBackend,
    }
    name_lower = name.lower()
    if name_lower not in backends:
        raise ValueError(f"未知 Tensor 后端: {name}. 可用后端: {list(backends.keys())}")

    backend = backends[name_lower]()
    if not backend.is_available():
        raise RuntimeError(f"Tensor 后端 '{name}' 不可用（未安装）")

    return backend
