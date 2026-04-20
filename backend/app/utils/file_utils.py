"""视频处理文件工具函数。"""

import os
import shutil
import tempfile
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_temp_dir(base_dir: str = None, prefix: str = "vp_") -> str:
    """创建临时目录并返回其路径。"""
    if base_dir:
        os.makedirs(base_dir, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix=prefix, dir=base_dir)
    else:
        temp_dir = tempfile.mkdtemp(prefix=prefix)
    logger.info(f"已创建临时目录: {temp_dir}")
    return temp_dir


def cleanup_dir(dir_path: str) -> None:
    """删除目录及其所有内容。"""
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
        logger.info(f"已清理目录: {dir_path}")


def validate_input_path(input_path: str) -> bool:
    """验证输入文件存在且为支持的视频格式。"""
    if not os.path.isfile(input_path):
        return False
    supported_extensions = {
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".webm",
        ".flv",
        ".wmv",
        ".ts",
        ".m2ts",
        ".vob",
    }
    _, ext = os.path.splitext(input_path)
    return ext.lower() in supported_extensions


def get_output_path(input_path: str, output_dir: str, suffix: str = "_output") -> str:
    """根据输入文件生成输出文件路径。"""
    basename = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{basename}{suffix}.mp4")


def ensure_dir(path: str) -> str:
    """确保目录存在，不存在则创建。"""
    os.makedirs(path, exist_ok=True)
    return path
