"""视频处理后端全局配置（CLI 模式）。"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量或默认值加载。"""

    # 应用
    APP_NAME: str = "视频补帧与超分软件"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # FFmpeg
    FFMPEG_PATH: str = r"D:\ffmpeg-2025-08-11-git-3542260376-full_build\bin\ffmpeg.exe"
    FFPROBE_PATH: str = r"D:\ffmpeg-2025-08-11-git-3542260376-full_build\bin\ffprobe.exe"

    # 处理参数
    TEMP_DIR: str = os.path.join(os.path.dirname(__file__), "..", "temp")
    OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "output")
    MAX_CONCURRENT_TASKS: int = 1

    # Tensor 后端: "pytorch" 或 "paddle"
    DEFAULT_TENSOR_BACKEND: str = "pytorch"

    # 日志配置
    LOG_DIR: str = os.path.join(os.path.dirname(__file__), "..", "logs")
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024  # 单文件最大 10MB
    LOG_FILE_BACKUP_COUNT: int = 5  # 保留 5 个轮转备份

    # RIFE 模型配置
    RIFE_MODEL_DIR: str = os.path.join(os.path.dirname(__file__), "..", "models")
    RIFE_MODEL_VERSION: str = "4.25"
    RIFE_SCALE: float = 1.0  # 处理分辨率缩放（0.5 适用于 4K 视频）
    RIFE_FP16: bool = False  # 是否使用半精度推理
    RIFE_DEFAULT_MULTI: int = 2  # 默认补帧倍率

    model_config = {"env_prefix": "VP_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
