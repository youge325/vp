"""视频补帧算法 — 基于 RIFE 的帧对插值实现。

支持 v4.0 ~ v4.26.heavy 全部 36 个模型版本。
"""

from __future__ import annotations

from app.utils.logger import get_logger
from typing import TYPE_CHECKING, Any


from app.algorithms.tensor_backend import ITensorBackend
from app.catalog.rife_models import SUPPORTED_MODELS as _RIFE_MODELS
from app.algorithms.pytorch.rife.onnx_solver import RIFEONNXSolver
from app.utils.model_metrics import get_rife_model_details

if TYPE_CHECKING:
    from app.algorithms.pytorch.rife.solver import RIFESolver

logger = get_logger(__name__)

SUPPORTED_ALGORITHMS: list[dict[str, Any]] = [
    {
        # RIFE 同时提供 PyTorch 与 ONNX 推理路径。
        "name": "rife",
        "family": "rife",
        "tensorBackends": ["pytorch", "onnx"],
        "models": list(_RIFE_MODELS),
        "modelDetails": get_rife_model_details(),
        "inputFrameMode": "none",
    },
]


class FrameInterpolationAlgorithm:
    """
    视频补帧算法 — 使用 RIFE 模型进行帧对插值。

    核心流程：
    1. 接收相邻两帧 (img0, img1) 和时间步 timestep
    2. RIFE 模型推理生成中间帧
    3. 支持可配置的插值倍率（2x, 4x 等）

    The stage descriptor declares pair mode; this implementation only exposes
    the pair operation required by that mode.
    """

    def __init__(
        self,
        tensor_backend: ITensorBackend,
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
        backend_name = tensor_backend.get_name()
        if backend_name not in {"pytorch", "onnx"}:
            raise ValueError(f"RIFE interpolation does not support the '{backend_name}' tensor backend.")
        self._tensor_backend = tensor_backend
        self._backend_name = backend_name
        self._multi = kwargs.get("multi", 2)
        self._model_version = kwargs.get("model_version", "4.25")
        self._scale = kwargs.get("scale", 1.0)
        self._fp16 = kwargs.get("fp16", False)
        self._device = kwargs.get("device", None)
        self._model_dir = kwargs.get("model_dir", "")
        self._onnx_model = kwargs.get("onnx_model")
        self._engine = kwargs.get("engine", "cuda")

        # 延迟初始化 RIFESolver
        self._solver: RIFESolver | RIFEONNXSolver | None = None

    def _ensure_solver(self):
        """延迟初始化 RIFE 推理器。"""
        if self._solver is not None:
            return self._solver

        if self._backend_name == "onnx":
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

    def process_frame_pair(self, frame0: Any, frame1: Any, timestep: float = 0.5, **_kwargs) -> Any:
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
        return solver.interpolate(frame0, frame1, timestep=timestep)
