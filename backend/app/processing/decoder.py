"""FFmpeg 解码器 — 将视频解码为帧序列（适配器模式）。"""

import os
from app.utils.logger import get_logger
from typing import Optional

from app.processing.pipeline import Filter
from app.utils.ffmpeg_wrapper import FFmpegWrapper

logger = get_logger(__name__)


class DecodeFilter(Filter):
    """
    使用 FFmpeg 将视频文件解码为 PNG 帧序列。

    输入: 包含 'input_path' 键的字典
    输出: 包含 'frame_dir', 'frame_prefix', 'fps', 'total_frames' 键的字典
    """

    def __init__(self, ffmpeg_wrapper: Optional[FFmpegWrapper] = None):
        self._ffmpeg = ffmpeg_wrapper or FFmpegWrapper()

    def process(self, data: dict, context: dict) -> dict:
        """将视频解码为帧序列。"""
        input_path = data.get("input_path")
        if not input_path or not os.path.isfile(input_path):
            raise FileNotFoundError(f"输入视频未找到: {input_path}")

        # 创建帧输出目录
        task_id = context.get("task_id", "unknown")
        temp_dir = context.get("temp_dir", os.path.join(os.path.dirname(__file__), "..", "..", "temp"))
        frame_dir = os.path.join(temp_dir, task_id, "frames")
        os.makedirs(frame_dir, exist_ok=True)

        logger.info(f"正在解码视频: {input_path} → {frame_dir}")

        # 获取视频信息
        fps = self._ffmpeg.get_fps(input_path)
        total_frames = self._ffmpeg.get_frame_count(input_path)

        # 解码为帧序列
        self._ffmpeg.decode_to_frames(input_path, frame_dir)

        # 统计实际解码的帧数
        actual_frames = len([f for f in os.listdir(frame_dir) if f.endswith(".png")])

        result = {
            **data,
            "frame_dir": frame_dir,
            "frame_prefix": "frame_%06d.png",
            "total_frames": actual_frames or total_frames,
            "original_fps": fps,
        }

        # 如果调用方未指定 fps，使用源帧率作为默认值
        if "fps" not in data:
            result["fps"] = fps

        # 更新上下文
        context["frame_dir"] = frame_dir
        context["total_frames"] = result["total_frames"]
        context["original_fps"] = fps

        return result

    def get_name(self) -> str:
        return "FFmpeg解码器"
