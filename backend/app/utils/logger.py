"""统一日志配置模块。

核心设计：
- CLI 模式下，日志输出到 stderr（避免与 stdout 的 JSON 行协议冲突）
- 同时写入日志文件（RotatingFileHandler，支持轮转）
- DEBUG 模式下自动降级日志级别为 DEBUG
- 提供 get_logger() 便捷函数，统一模块 logger 创建方式
"""

from datetime import datetime
import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

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
_STARTUP_LOG_FILE_RE = re.compile(r"^(?P<base>app-\d{8}-\d{6}-\d{6}\.log)(?:\.\d+)?$")


def _load_settings():
    try:
        from app.config import settings
    except ImportError:
        return None
    return settings


def _default_log_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "logs")


def _build_startup_log_file(log_dir: str | Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return Path(log_dir) / f"app-{timestamp}.log"


def _collect_startup_log_groups(log_dir: Path) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for path in log_dir.iterdir():
        if not path.is_file():
            continue

        match = _STARTUP_LOG_FILE_RE.match(path.name)
        if match is None:
            continue

        groups.setdefault(match.group("base"), []).append(path)
    return groups


def _cleanup_old_startup_logs(log_dir: Path, keep_count: int, current_log_file: Path) -> None:
    keep_count = max(int(keep_count), 1)
    groups = _collect_startup_log_groups(log_dir)
    groups.setdefault(current_log_file.name, [])

    expired_group_names = sorted(groups, reverse=True)[keep_count:]
    for group_name in expired_group_names:
        for path in groups[group_name]:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except OSError:
                continue


def setup_logging() -> None:
    """根据应用 settings 一次性配置全局日志系统。"""
    global _initialized
    if _initialized:
        return

    settings = _load_settings()
    if settings is not None:
        level = logging.DEBUG if settings.DEBUG else logging.INFO
        log_dir = settings.LOG_DIR
        log_file_max_bytes = settings.LOG_FILE_MAX_BYTES
        log_file_backup_count = settings.LOG_FILE_BACKUP_COUNT
        log_startup_file_keep_count = settings.LOG_STARTUP_FILE_KEEP_COUNT
    else:
        level = logging.INFO
        log_dir = _default_log_dir()
        log_file_max_bytes = 10 * 1024 * 1024
        log_file_backup_count = 5
        log_startup_file_keep_count = 30

    # 确保日志目录存在
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_file = _build_startup_log_file(log_dir_path)
    _cleanup_old_startup_logs(log_dir_path, log_startup_file_keep_count, log_file)

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
    root.debug(
        "日志系统初始化完成: level=%s, log_dir=%s, log_file=%s",
        logging.getLevelName(level),
        log_dir_path,
        log_file,
    )


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger 的便捷函数。

    用法:
        logger = get_logger(__name__)

    如果日志系统尚未初始化，自动以默认配置初始化。
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(name)
