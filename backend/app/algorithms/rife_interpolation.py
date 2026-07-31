"""RIFE frame-pair interpolation implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.algorithms.pytorch.rife.onnx_solver import RIFEONNXSolver
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.algorithms.pytorch.rife.solver import RIFESolver

logger = get_logger(__name__)


class FrameInterpolationAlgorithm:
    """Generate intermediate frames with the selected RIFE runtime."""

    def __init__(
        self,
        *,
        backend_name: str,
        model_version: str,
        scale: float,
        fp16: bool,
        onnx_model: str | None,
        engine: str,
        model_dir: str,
    ) -> None:
        if backend_name not in {"pytorch", "onnx"}:
            raise ValueError(f"RIFE interpolation does not support the '{backend_name}' tensor backend.")
        self._backend_name = backend_name
        self._model_version = model_version
        self._scale = scale
        self._fp16 = fp16
        self._model_dir = model_dir
        self._onnx_model = onnx_model
        self._engine = engine
        self._solver: RIFESolver | RIFEONNXSolver | None = None

    def _ensure_solver(self) -> RIFESolver | RIFEONNXSolver:
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
                f"scale={self._scale}, fp16={self._fp16}, engine={self._engine}"
            )
            from app.algorithms.pytorch.rife.solver import RIFESolver

            self._solver = RIFESolver(
                model_version=self._model_version,
                scale=self._scale,
                fp16=self._fp16,
                model_dir=self._model_dir,
                engine=self._engine,
            )
        return self._solver

    def process_frame_pair(self, frame0: Any, frame1: Any, *, timestep: float) -> Any:
        return self._ensure_solver().interpolate(frame0, frame1, timestep=timestep)
