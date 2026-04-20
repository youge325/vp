"""统一日志配置模块。

核心设计：
- CLI 模式下，日志输出到 stderr（避免与 stdout 的 JSON 行协议冲突）
- 同时写入日志文件（RotatingFileHandler，支持轮转）
- DEBUG 模式下自动降级日志级别为 DEBUG
- 提供 get_logger() 便捷函数，统一模块 logger 创建方式
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# 日志格式
# ---------------------------------------------------------------------------

# 控制台格式（stderr）：简洁，用于开发调试
_CONSOLE_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_CONSOLE_DATE_FMT = "%H:%M:%S"

# 文件格式：详细，包含文件名和行号，用于事后排查
_FILE_FMT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
_FILE_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# 模块级状态
# ---------------------------------------------------------------------------

_initialized = False


def setup_logging(
    level: str | int | None = None,
    log_dir: str | None = None,
    log_file_max_bytes: int = 10 * 1024 * 1024,
    log_file_backup_count: int = 5,
    force: bool = False,
) -> None:
    """一次性配置全局日志系统。

    参数:
        level: 日志级别（"DEBUG"/"INFO"/"WARNING"/"ERROR"）。
               默认从 config.settings 读取，DEBUG=True 时自动降为 DEBUG。
        log_dir: 日志文件目录。默认为 backend/logs/。
        log_file_max_bytes: 单个日志文件最大字节数（默认 10MB）。
        log_file_backup_count: 保留的轮转备份文件数（默认 5）。
        force: 是否强制重新配置（默认 False，重复调用时跳过）。
    """
    global _initialized
    if _initialized and not force:
        return

    # 确定日志级别
    if level is None:
        try:
            from app.config import settings

            level = logging.DEBUG if settings.DEBUG else logging.INFO
        except ImportError:
            level = logging.INFO
    elif isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # 确定 log_dir
    if log_dir is None:
        try:
            from app.config import settings

            log_dir = settings.LOG_DIR
        except (ImportError, AttributeError):
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 获取根 logger
    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有 handler（避免 basicConfig 残留或重复配置）
    root.handlers.clear()

    # --- Handler 1: 控制台（stderr，避免与 stdout JSON 行协议冲突）---
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FMT, _CONSOLE_DATE_FMT))
    root.addHandler(console_handler)

    # --- Handler 2: 日志文件（轮转）---
    log_file = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=log_file_max_bytes,
        backupCount=log_file_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FILE_FMT, _FILE_DATE_FMT))
    root.addHandler(file_handler)

    # 降低第三方库日志噪音
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("pydot").setLevel(logging.WARNING)

    _initialized = True

    # 用 root logger 记录初始化完成
    root.debug("日志系统初始化完成: level=%s, log_dir=%s", logging.getLevelName(level), log_dir)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger 的便捷函数。

    用法:
        logger = get_logger(__name__)

    如果日志系统尚未初始化，自动以默认配置初始化。
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(name)
