"""FFmpeg 封装工具测试。"""

import os
import pytest
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.config import settings


class TestFFmpegWrapper:
    """测试 FFmpegWrapper 类。"""

    def test_init_default_paths(self):
        wrapper = FFmpegWrapper()
        assert wrapper.ffmpeg_path == settings.FFMPEG_PATH
        assert wrapper.ffprobe_path == settings.FFPROBE_PATH

    def test_init_custom_paths(self):
        wrapper = FFmpegWrapper(ffmpeg_path="/custom/ffmpeg", ffprobe_path="/custom/ffprobe")
        assert wrapper.ffmpeg_path == "/custom/ffmpeg"
        assert wrapper.ffprobe_path == "/custom/ffprobe"

    def test_is_available_with_default_path(self):
        wrapper = FFmpegWrapper()
        result = wrapper.is_available()
        assert isinstance(result, bool)

    def test_is_available_with_nonexistent_path(self):
        wrapper = FFmpegWrapper(ffmpeg_path="/nonexistent/ffmpeg")
        assert wrapper.is_available() is False

    def test_get_video_info_nonexistent_file(self):
        wrapper = FFmpegWrapper()
        # FFmpeg/ffprobe 可能抛出 FileNotFoundError（二进制未找到）或 RuntimeError（命令执行失败）
        with pytest.raises((RuntimeError, FileNotFoundError)):
            wrapper.get_video_info("/nonexistent/file.mp4")

    def test_decode_nonexistent_file(self):
        wrapper = FFmpegWrapper()
        with pytest.raises((RuntimeError, FileNotFoundError)):
            wrapper.decode_to_frames("/nonexistent/file.mp4", "/tmp/test_frames")

    def test_encode_nonexistent_dir(self):
        wrapper = FFmpegWrapper()
        with pytest.raises((RuntimeError, FileNotFoundError)):
            wrapper.encode_from_frames("/nonexistent/frames", "/tmp/output.mp4")

    def test_is_available_with_actual_ffmpeg(self):
        """测试使用配置的 FFmpeg 路径。"""
        wrapper = FFmpegWrapper()
        if os.path.isfile(settings.FFMPEG_PATH):
            assert wrapper.is_available() is True
        else:
            assert wrapper.is_available() is False
