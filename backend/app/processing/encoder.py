"""FFmpeg 编码器 — 将帧序列编码为视频并合并音频（适配器模式）。"""

import os
import shutil
from app.utils.logger import get_logger
from typing import Optional

from app.processing.pipeline import Filter
from app.utils.ffmpeg_wrapper import FFmpegWrapper

logger = get_logger(__name__)


class EncodeFilter(Filter):
    """
    将帧序列编码为输出视频并合并音频。

    输入: 包含 'frame_dir', 'output_path', 'fps' 键的字典
    输出: 包含 'output_path', 'audio_merged' 键的字典
    """

    def __init__(
        self,
        ffmpeg_wrapper: Optional[FFmpegWrapper] = None,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
    ):
        self._ffmpeg = ffmpeg_wrapper or FFmpegWrapper()
        self.codec = codec
        self.crf = crf
        self.preset = preset

    def process(self, data: dict, context: dict) -> dict:
        """将帧序列编码为视频并合并音频。"""
        frame_dir = data.get("frame_dir")
        if not frame_dir or not os.path.isdir(frame_dir):
            raise FileNotFoundError(f"帧目录未找到: {frame_dir}")

        output_path = data.get("output_path")
        if not output_path:
            output_dir = context.get(
                "output_dir",
                os.path.join(os.path.dirname(__file__), "..", "..", "output"),
            )
            os.makedirs(output_dir, exist_ok=True)
            task_id = context.get("task_id", "unknown")
            output_path = os.path.join(output_dir, f"{task_id}_output.mp4")

        fps = data.get("fps", 60.0)
        input_path = data.get("input_path", "")
        frame_prefix = data.get("frame_prefix", "frame_%06d.png")

        # 支持目标帧率模式：从 context 获取 target_fps 进行帧率压制
        target_fps = context.get("target_fps")
        output_fps = target_fps if target_fps is not None else None

        if output_fps is not None:
            logger.info(f"正在编码帧序列: {frame_dir} → {output_path} @ {fps}fps → {output_fps}fps (帧率压制)")
        else:
            logger.info(f"正在编码帧序列: {frame_dir} → {output_path} @ {fps}fps")

        # 第一步：将帧序列编码为视频（不含音频）
        temp_video = output_path.replace(".mp4", "_noaudio.mp4")
        self._ffmpeg.encode_from_frames(
            frame_dir=frame_dir,
            output_path=temp_video,
            fps=fps,
            output_fps=output_fps,
            frame_prefix=frame_prefix,
            codec=self.codec,
            crf=self.crf,
            preset=self.preset,
        )

        # 第二步：从原始视频合并音频
        audio_merged = False
        if input_path and os.path.isfile(input_path):
            temp_dir = os.path.dirname(frame_dir)
            temp_audio = os.path.join(temp_dir, "audio.aac")

            try:
                audio_path = self._ffmpeg.extract_audio(input_path, temp_audio)
                if audio_path and os.path.isfile(audio_path):
                    final_path = self._ffmpeg.merge_audio(temp_video, audio_path, output_path)
                    audio_merged = final_path == output_path
                    # 清理临时文件
                    if os.path.isfile(temp_audio):
                        os.remove(temp_audio)
                    if os.path.isfile(temp_video) and temp_video != output_path:
                        os.remove(temp_video)
                else:
                    # 无音频轨道，直接移动
                    if os.path.isfile(temp_video):
                        shutil.move(temp_video, output_path)
            except Exception as e:
                logger.warning(f"音频合并失败: {e}")
                if os.path.isfile(temp_video):
                    shutil.move(temp_video, output_path)
        else:
            if os.path.isfile(temp_video):
                shutil.move(temp_video, output_path)

        result = {
            **data,
            "output_path": output_path,
            "audio_merged": audio_merged,
        }

        return result

    def get_name(self) -> str:
        return "FFmpeg编码器"
