"""视频补帧算法 — 基于 RIFE 的帧对插值实现。

支持 v4.0 ~ v4.26.heavy 全部 36 个模型版本。
"""

from __future__ import annotations

from app.utils.logger import get_logger
from typing import TYPE_CHECKING, Any, Optional


from app.algorithms.base import IAlgorithm
from app.algorithms.tensor_backend import ITensorBackend
from app.algorithms.pytorch.rife.model_loader import SUPPORTED_MODELS as _RIFE_MODELS
from app.algorithms.pytorch.rife.onnx_solver import RIFEONNXSolver

if TYPE_CHECKING:
    from app.algorithms.pytorch.rife.solver import RIFESolver

logger = get_logger(__name__)

SUPPORTED_ALGORITHMS: list[dict[str, Any]] = [
    {
        # Phase 8 — ``tensorBackends`` 显式声明该算法支持的 tensor
        # 后端集合。RIFE 同时提供 PyTorch 实现 (algorithms/pytorch/rife/)
        # 与 ONNX 推理路径,因此两者都列出;paddle 暂无实现,前端切到
        # paddle 后该算法不会出现在下拉列表里。
        "name": "rife",
        "tensorBackends": ["pytorch", "onnx"],
        "models": list(_RIFE_MODELS),
    },
]


class FrameInterpolationAlgorithm(IAlgorithm):
    """
    视频补帧算法 — 使用 RIFE 模型进行帧对插值。

    核心流程：
    1. 接收相邻两帧 (img0, img1) 和时间步 timestep
    2. RIFE 模型推理生成中间帧
    3. 支持可配置的插值倍率（2x, 4x 等）

    使用方式：
    - needs_frame_pairs() 返回 True，通知流式处理器使用帧对处理模式
    - process_frame_pair() 实现帧对插值推理
    - process_frame() 保留兼容但标记为不支持（补帧需要帧对）
    """

    def __init__(
        self,
        tensor_backend: Optional[ITensorBackend] = None,
        **kwargs,
    ):
        """
        参数:
            tensor_backend: Tensor 后端（当前未使用，RIFE 直接使用 PyTorch）
            **kwargs: 额外参数
                - multi: 补帧倍率（2=2x, 4=4x），默认 2
                - model_version: RIFE 模型版本，默认 "4.25"
                - scale: 处理分辨率缩放，默认 1.0
                - fp16: 是否使用半精度推理，默认 False
                - device: 推理设备，默认自动选择
                - model_dir: 模型权重目录，默认空字符串
        """
        self._tensor_backend = tensor_backend
        self._multi = kwargs.get("multi", 2)
        self._model_version = kwargs.get("model_version", "4.25")
        self._scale = kwargs.get("scale", 1.0)
        self._fp16 = kwargs.get("fp16", False)
        self._device = kwargs.get("device", None)
        self._model_dir = kwargs.get("model_dir", "")
        self._onnx_model = kwargs.get("onnx_model")
        self._engine = kwargs.get("engine", "cuda")

        # 延迟初始化 RIFESolver
        self._solver: Optional[RIFESolver] = None

    def _ensure_solver(self):
        """延迟初始化 RIFE 推理器。"""
        if self._solver is not None:
            return self._solver

        backend_name = self._tensor_backend.get_name() if self._tensor_backend is not None else "numpy"

        if backend_name == "onnx":
            logger.info(f"初始化 RIFE ONNX 推理器: v{self._model_version}, engine={self._engine}")
            self._solver = RIFEONNXSolver(
                model_version=self._model_version,
                model_dir=self._model_dir,
                onnx_model=self._onnx_model,
                engine=self._engine,
            )
        else:
            logger.info(
                f"初始化 RIFE PyTorch 推理器: v{self._model_version}, "
                f"multi={self._multi}x, scale={self._scale}, fp16={self._fp16}, engine={self._engine}"
            )
            from app.algorithms.pytorch.rife.solver import RIFESolver

            self._solver = RIFESolver(
                model_version=self._model_version,
                scale=self._scale,
                device=self._device,
                fp16=self._fp16,
                model_dir=self._model_dir,
                engine=self._engine,
            )
        return self._solver

    # ------------------------------------------------------------------
    # IAlgorithm 接口实现
    # ------------------------------------------------------------------

    def process_frame(self, frame: Any, **kwargs) -> Any:
        """
        单帧处理（补帧算法不适用，直接返回原帧）。

        补帧需要帧对输入；如果流式处理链在单帧回退路径上调用这里，
        则仅原样返回输入帧。
        """
        return frame

    def process_frame_batch(self, frames: list[Any], **kwargs) -> list[Any]:
        """
        批量帧处理（补帧算法不适用，直接返回原帧列表）。
        """
        return frames

    def get_name(self) -> str:
        return f"补帧算法(RIFE v{self._model_version}, {self._multi}x)"

    def validate(self) -> bool:
        """验证 RIFE 模型是否可运行。"""
        backend_name = self._tensor_backend.get_name() if self._tensor_backend is not None else "numpy"
        if backend_name == "onnx":
            return True

        try:
            import torch

            if not torch.cuda.is_available() and self._device in (None, "cuda"):
                logger.warning("CUDA 不可用，将使用 CPU 推理（速度较慢）")
            return True
        except ImportError:
            logger.error("PyTorch 未安装，RIFE 算法不可用")
            return False

    def get_description(self) -> str:
        return (
            f"基于 RIFE v{self._model_version} 的视频补帧算法。"
            f"支持 {self._multi}x 插值倍率，"
            f"{'半精度' if self._fp16 else '全精度'}推理。"
        )

    # ------------------------------------------------------------------
    # 帧对处理接口
    # ------------------------------------------------------------------

    def needs_frame_pairs(self) -> bool:
        """补帧算法需要帧对处理模式。"""
        return True

    def process_frame_pair(self, frame0: Any, frame1: Any, timestep: float = 0.5, **kwargs) -> Any:
        """
        使用 RIFE 模型对帧对进行插值，生成中间帧。

        参数:
            frame0: 前一帧 Tensor（由当前 tensor_backend 转换）
            frame1: 后一帧 Tensor（由当前 tensor_backend 转换）
            timestep: 插值时间步 (0.0=frame0, 1.0=frame1)

        返回:
            中间帧 Tensor（由当前 tensor_backend 转换）
        """
        solver = self._ensure_solver()
        backend_name = self._tensor_backend.get_name() if self._tensor_backend is not None else "numpy"

        # PyTorch backend: 直接传递 torch tensor（零开销）
        if backend_name == "pytorch":
            return solver.interpolate(frame0, frame1, timestep=timestep)

        # ONNX backend: 直接传递 numpy ndarray（零开销）
        if backend_name == "onnx":
            return solver.interpolate(frame0, frame1, timestep=timestep)

        # 其他 backend: 做 numpy 桥接
        import numpy as np
        import torch

        np0 = frame0 if self._tensor_backend is None else self._tensor_backend.tensor_to_numpy(frame0)
        np1 = frame1 if self._tensor_backend is None else self._tensor_backend.tensor_to_numpy(frame1)

        t0 = torch.from_numpy(np.transpose(np0, (2, 0, 1)).copy()).unsqueeze(0).float() / 255.0
        t1 = torch.from_numpy(np.transpose(np1, (2, 0, 1)).copy()).unsqueeze(0).float() / 255.0
        if torch.cuda.is_available():
            t0 = t0.cuda()
            t1 = t1.cuda()

        result = solver.interpolate(t0, t1, timestep=timestep)
        result_np = (result[0] * 255.0).byte().cpu().numpy().transpose(1, 2, 0)

        if self._tensor_backend is not None:
            return self._tensor_backend.numpy_to_tensor(result_np)
        return result_np

    def get_interpolation_multi(self) -> int:
        """返回补帧倍率。"""
        return self._multi
