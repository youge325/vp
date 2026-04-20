"""帧处理过滤器 — 支持逐帧处理和帧对插值两种模式。"""

import os
from app.utils.logger import get_logger
from typing import Optional, Callable

import numpy as np
from PIL import Image

from app.processing.pipeline import Filter
from app.algorithms.base import IAlgorithm
from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import ITensorBackend, get_tensor_backend

logger = get_logger(__name__)


class FrameProcessFilter(Filter):
    """
    通过 Tensor 后端应用算法处理帧。

    支持两种处理模式：
    1. 逐帧处理模式（默认）：每帧独立处理，1 输入帧 → 1 输出帧
       适用于超分、动漫优化等算法
    2. 帧对插值模式：对相邻帧对生成中间帧，N 输入帧 → N + (N-1)*(multi-1) 输出帧
       适用于补帧算法（RIFE），算法需实现 needs_frame_pairs()=True

    输入: 包含 'frame_dir', 'total_frames' 键的字典
    输出: 包含 'frame_dir', 'processed_frames' 键的字典
    """

    def __init__(
        self,
        algorithm: Optional[IAlgorithm] = None,
        algorithm_type: str = "frame_interpolation",
        tensor_backend_name: str = "pytorch",
        progress_callback: Optional[Callable[[int, int], None]] = None,
        algorithm_kwargs: Optional[dict] = None,
        stage_name: Optional[str] = None,
    ):
        """
        参数:
            algorithm: 预创建的算法实例（为 None 时由工厂创建）
            algorithm_type: 从工厂创建的算法类型
            tensor_backend_name: 使用的 Tensor 后端（'pytorch' 或 'paddle'）
            progress_callback: 可选的进度回调函数 callback(当前帧, 总帧数)
            algorithm_kwargs: 传递给算法工厂的额外参数（如 multi, model_version 等）
        """
        self._tensor_backend_name = tensor_backend_name
        self._tensor_backend: Optional[ITensorBackend] = None
        self._algorithm = algorithm
        self._algorithm_type = algorithm_type
        self._progress_callback = progress_callback
        self._algorithm_kwargs = algorithm_kwargs or {}
        self._stage_name = stage_name or algorithm_type

    def _ensure_backend(self):
        """延迟初始化 Tensor 后端。"""
        if self._tensor_backend is None:
            self._tensor_backend = get_tensor_backend(self._tensor_backend_name)
            logger.info(f"使用 Tensor 后端: {self._tensor_backend.get_name()}")

    def _ensure_algorithm(self):
        """延迟初始化算法。"""
        if self._algorithm is None:
            self._algorithm = AlgorithmFactory.create(
                algorithm_type=self._algorithm_type,
                tensor_backend_name=self._tensor_backend_name,
                **self._algorithm_kwargs,
            )
            logger.info(f"使用算法: {self._algorithm.get_name()}")

    def process(self, data: dict, context: dict) -> dict:
        """处理帧目录中的所有帧。"""
        self._ensure_backend()
        self._ensure_algorithm()

        frame_dir = data.get("frame_dir")
        if not frame_dir or not os.path.isdir(frame_dir):
            raise FileNotFoundError(f"帧目录未找到: {frame_dir}")

        # 获取排序后的帧文件列表
        frame_files = sorted([f for f in os.listdir(frame_dir) if f.endswith(".png")])
        total_frames = len(frame_files)

        logger.info(
            f"正在处理 {total_frames} 帧，算法 '{self._algorithm.get_name()}'，后端 '{self._tensor_backend.get_name()}'"
        )

        # 根据算法类型选择处理模式
        if self._algorithm.needs_frame_pairs():
            result = self._process_frame_pairs(data, context, frame_files)
        else:
            result = self._process_single_frames(data, context, frame_files)

        return result

    def _process_single_frames(self, data: dict, context: dict, frame_files: list[str]) -> dict:
        """逐帧处理模式：每帧独立处理。"""
        total_frames = len(frame_files)
        frame_dir = data.get("frame_dir")

        processed_dir = self._get_processed_dir(frame_dir)
        os.makedirs(processed_dir, exist_ok=True)

        for i, frame_file in enumerate(frame_files):
            frame_path = os.path.join(frame_dir, frame_file)

            # numpy → Tensor → 算法处理 → Tensor → numpy
            frame_np = np.array(Image.open(frame_path))
            tensor = self._tensor_backend.numpy_to_tensor(frame_np)
            processed_tensor = self._algorithm.process_frame(tensor)
            result_np = self._tensor_backend.tensor_to_numpy(processed_tensor)

            # 保存处理后的帧
            output_path = os.path.join(processed_dir, frame_file)
            Image.fromarray(result_np).save(output_path)

            # 报告进度
            if self._progress_callback:
                self._progress_callback(i + 1, total_frames)

        # 更新数据
        result = {
            **data,
            "frame_dir": processed_dir,
            "processed_frames": total_frames,
            "frame_prefix": data.get("frame_prefix", "frame_%06d.png"),
        }
        context["processed_frames"] = total_frames
        return result

    def _process_frame_pairs(self, data: dict, context: dict, frame_files: list[str]) -> dict:
        """
        帧对插值模式：对每对相邻帧生成中间帧。

        输出帧序列：F0, mid01_1, ..., mid01_(multi-1), F1, mid12_1, ..., Fn
        输出帧数 = N + (N-1) * (multi-1)
        输出 fps = original_fps * multi
        """
        import torch

        total_frames = len(frame_files)
        if total_frames < 2:
            logger.warning("帧数不足 2，无法进行补帧，回退到逐帧处理")
            return self._process_single_frames(data, context, frame_files)

        frame_dir = data.get("frame_dir")
        multi = self._algorithm.get_interpolation_multi()

        processed_dir = self._get_processed_dir(frame_dir)
        os.makedirs(processed_dir, exist_ok=True)

        # 计算总输出帧数
        output_frame_count = total_frames + (total_frames - 1) * (multi - 1)
        logger.info(
            f"补帧模式: {total_frames} 帧 → {output_frame_count} 帧 ({multi}x, 每对帧生成 {multi - 1} 个中间帧)"
        )

        output_idx = 0

        for i in range(total_frames - 1):
            # 读取帧对
            img0_np = np.array(Image.open(os.path.join(frame_dir, frame_files[i])))
            img1_np = np.array(Image.open(os.path.join(frame_dir, frame_files[i + 1])))

            # numpy → Tensor（CHW float32 [0,1]）
            img0 = torch.from_numpy(img0_np).permute(2, 0, 1).unsqueeze(0).float() / 255.0
            img1 = torch.from_numpy(img1_np).permute(2, 0, 1).unsqueeze(0).float() / 255.0

            # 写入前一帧（原始帧）
            self._save_output_frame(img0, processed_dir, output_idx)
            output_idx += 1

            # 生成中间帧
            for j in range(1, multi):
                timestep = j / multi
                mid_tensor = self._algorithm.process_frame_pair(img0, img1, timestep=timestep)
                self._save_output_frame(mid_tensor, processed_dir, output_idx)
                output_idx += 1

            # 报告进度（每完成一对帧）
            if self._progress_callback:
                self._progress_callback(i + 1, total_frames - 1)

        # 写入最后一帧
        last_np = np.array(Image.open(os.path.join(frame_dir, frame_files[-1])))
        last_tensor = torch.from_numpy(last_np).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        self._save_output_frame(last_tensor, processed_dir, output_idx)
        output_idx += 1

        # 更新 fps：补帧后帧率 = 原始帧率 * multi
        # 使用 original_fps（源视频帧率）而非 fps（可能已被用户指定为目标帧率）
        original_fps = data.get("original_fps", data.get("fps", 30.0))
        new_fps = original_fps * multi
        logger.info(f"补帧完成: {output_idx} 帧, fps {original_fps} → {new_fps}")

        # 更新数据和上下文
        result = {
            **data,
            "frame_dir": processed_dir,
            "processed_frames": output_idx,
            "fps": new_fps,
            "frame_prefix": "frame_%08d.png",
        }
        context["processed_frames"] = output_idx
        context["fps"] = new_fps

        return result

    def _get_processed_dir(self, frame_dir: str) -> str:
        """为当前处理阶段生成独立的输出目录。"""
        safe_stage_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in self._stage_name)
        return os.path.join(os.path.dirname(frame_dir), f"processed_{safe_stage_name}")

    @staticmethod
    def _save_output_frame(tensor: "torch.Tensor", output_dir: str, frame_idx: int) -> None:
        """
        将 Tensor 帧保存为 PNG 文件。

        参数:
            tensor: 帧张量，形状 (1, 3, H, W)，值域 [0, 1]
            output_dir: 输出目录
            frame_idx: 帧编号（用于文件命名）
        """
        # Tensor → numpy (HWC, uint8)
        frame_np = (tensor.detach().cpu().squeeze(0).permute(1, 2, 0).clamp(0, 1).numpy() * 255).astype(np.uint8)
        filename = f"frame_{frame_idx:08d}.png"
        Image.fromarray(frame_np).save(os.path.join(output_dir, filename))

    def get_name(self) -> str:
        return f"帧处理器({self._algorithm_type})"
