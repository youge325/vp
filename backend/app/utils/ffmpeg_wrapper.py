"""FFmpeg 命令行封装 — 适配器模式，集成 FFmpeg 功能。"""

import json
from app.utils.logger import get_logger
import os
import shutil
import subprocess
from typing import Optional

from app.config import settings

logger = get_logger(__name__)


class FFmpegWrapper:
    """封装 FFmpeg/FFprobe 命令行调用，提供视频处理操作。"""

    def __init__(
        self,
        ffmpeg_path: str = None,
        ffprobe_path: str = None,
    ):
        self._ffmpeg_path_explicit = ffmpeg_path is not None
        self._ffprobe_path_explicit = ffprobe_path is not None
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH
        self.ffprobe_path = ffprobe_path or settings.FFPROBE_PATH
        # 自动检测：仅在未手动指定路径时，尝试从 PATH 中查找
        self._auto_detect_paths()

    # ------------------------------------------------------------------
    # 视频信息
    # ------------------------------------------------------------------

    def get_video_info(self, input_path: str) -> dict:
        """使用 ffprobe 获取视频元数据。"""
        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]
        result = self._run_command(cmd)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}

    def get_fps(self, input_path: str) -> float:
        """获取视频文件的帧率。"""
        info = self.get_video_info(input_path)
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                # r_frame_rate 格式为 "30/1" 或 "24000/1001"
                r_frame_rate = stream.get("r_frame_rate", "30/1")
                parts = r_frame_rate.split("/")
                if len(parts) == 2 and int(parts[1]) != 0:
                    return round(int(parts[0]) / int(parts[1]), 3)
                return 30.0
        return 30.0

    def get_frame_count(self, input_path: str) -> int:
        """获取视频文件的总帧数。"""
        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-print_format",
            "json",
            input_path,
        ]
        result = self._run_command(cmd)
        try:
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            if streams:
                return int(streams[0].get("nb_read_frames", 0))
        except (json.JSONDecodeError, ValueError, IndexError):
            pass
        # 回退方案：根据时长 × 帧率估算
        info = self.get_video_info(input_path)
        duration = float(info.get("format", {}).get("duration", 0))
        fps = self.get_fps(input_path)
        return int(duration * fps) if duration > 0 else 0

    def get_duration(self, input_path: str) -> float:
        """获取视频文件时长（秒）。"""
        info = self.get_video_info(input_path)
        return float(info.get("format", {}).get("duration", 0))

    def has_audio(self, input_path: str) -> bool:
        """检查视频文件是否包含音频流。"""
        info = self.get_video_info(input_path)
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "audio":
                return True
        return False

    # ------------------------------------------------------------------
    # 解码（视频 → 帧序列）
    # ------------------------------------------------------------------

    def decode_to_frames(
        self,
        input_path: str,
        output_dir: str,
        frame_prefix: str = "frame_%06d.png",
    ) -> str:
        """
        将视频文件解码为 PNG 帧序列。

        返回输出目录路径。
        """
        os.makedirs(output_dir, exist_ok=True)
        output_pattern = os.path.join(output_dir, frame_prefix)

        cmd = [
            self.ffmpeg_path,
            "-i",
            input_path,
            "-qscale:v",
            "1",
            "-qmin",
            "1",
            "-qmax",
            "1",
            "-vsync",
            "0",
            output_pattern,
            "-y",
        ]
        self._run_command(cmd)
        logger.info(f"已解码 {input_path} → {output_dir}")
        return output_dir

    # ------------------------------------------------------------------
    # 编码（帧序列 → 视频）
    # ------------------------------------------------------------------

    def encode_from_frames(
        self,
        frame_dir: str,
        output_path: str,
        fps: float = 60.0,
        output_fps: float = None,
        frame_prefix: str = "frame_%06d.png",
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
    ) -> str:
        """
        将帧序列编码为视频文件。

        参数:
            frame_dir: 帧目录路径
            output_path: 输出文件路径
            fps: 输入帧率（-framerate 参数，决定读取帧的速率）
            output_fps: 输出帧率（-r 参数，决定最终视频帧率）。
                        如果指定且与 fps 不同，FFmpeg 会做帧率转换（压制/丢帧）。
                        为 None 时不设 -r 参数，输出帧率等于输入帧率。
            frame_prefix: 帧文件名模板
            codec: 视频编码器
            crf: CRF 质量值
            preset: 编码预设

        返回输出文件路径。
        """
        input_pattern = os.path.join(frame_dir, frame_prefix)

        cmd = [
            self.ffmpeg_path,
            "-framerate",
            str(fps),
            "-i",
            input_pattern,
        ]

        # 如果指定了输出帧率且与输入帧率不同，添加 -r 参数做帧率转换
        if output_fps is not None and abs(output_fps - fps) > 0.01:
            cmd.extend(["-r", str(output_fps)])
            logger.info(f"帧率压制: 输入 {fps}fps → 输出 {output_fps}fps")

        cmd.extend(
            [
                "-c:v",
                codec,
                "-crf",
                str(crf),
                "-preset",
                preset,
                "-pix_fmt",
                "yuv420p",
                output_path,
                "-y",
            ]
        )
        self._run_command(cmd)
        logger.info(f"已编码 {frame_dir} → {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # 音频操作
    # ------------------------------------------------------------------

    def extract_audio(self, input_path: str, output_path: str) -> Optional[str]:
        """从视频文件中提取音频轨道。"""
        cmd = [
            self.ffmpeg_path,
            "-i",
            input_path,
            "-vn",  # 不含视频
            "-acodec",
            "copy",
            output_path,
            "-y",
        ]
        try:
            self._run_command(cmd)
            if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"已提取音频: {output_path}")
                return output_path
        except Exception as e:
            logger.warning(f"音频提取失败: {e}")
        return None

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """将音频轨道合并到视频文件中。"""
        cmd = [
            self.ffmpeg_path,
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            output_path,
            "-y",
        ]
        self._run_command(cmd)
        logger.info(f"已合并音频: {video_path} + {audio_path} → {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # 格式转换
    # ------------------------------------------------------------------

    def convert_format(
        self,
        input_path: str,
        output_path: str,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
        audio_codec: str = "aac",
    ) -> str:
        """使用指定编码器转换视频格式。"""
        cmd = [
            self.ffmpeg_path,
            "-i",
            input_path,
            "-c:v",
            codec,
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-c:a",
            audio_codec,
            output_path,
            "-y",
        ]
        self._run_command(cmd)
        logger.info(f"已转换: {input_path} → {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _run_command(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """执行命令并返回结果。"""
        logger.debug(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,  # 1 小时超时
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"FFmpeg 命令执行失败 (退出码 {result.returncode}): {error_msg}")
        return result

    def is_available(self) -> bool:
        """检查 FFmpeg 可执行文件是否可用（通过 ffmpeg -version 检测）。"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False

    def get_version(self) -> Optional[str]:
        """获取 FFmpeg 版本信息。"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if result.returncode == 0:
                # 输出第一行通常为 "ffmpeg version 6.1.2-full_build ..."
                first_line = result.stdout.strip().split("\n")[0]
                return first_line
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            pass
        return None

    def _auto_detect_paths(self):
        """仅在未手动指定路径时，从系统 PATH 中自动查找 ffmpeg/ffprobe。"""
        if not self._ffmpeg_path_explicit and not os.path.isfile(self.ffmpeg_path):
            found = shutil.which("ffmpeg")
            if found:
                logger.info(f"配置的 FFmpeg 路径不存在，自动检测到: {found}")
                self.ffmpeg_path = found

        if not self._ffprobe_path_explicit and not os.path.isfile(self.ffprobe_path):
            found = shutil.which("ffprobe")
            if found:
                logger.info(f"配置的 FFprobe 路径不存在，自动检测到: {found}")
                self.ffprobe_path = found
