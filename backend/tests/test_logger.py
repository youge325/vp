import logging
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

import app.utils.logger as logger_module


def _get_file_handler() -> RotatingFileHandler:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, RotatingFileHandler):
            return handler
    raise AssertionError("未找到日志文件 handler")


def _make_startup_log_files(log_dir: Path, index: int) -> tuple[Path, Path]:
    log_name = f"app-20240101-0000{index:02d}-000000.log"
    log_file = log_dir / log_name
    rotated_file = log_dir / f"{log_name}.1"
    log_file.write_text(f"log-{index}", encoding="utf-8")
    rotated_file.write_text(f"log-{index}-rotated", encoding="utf-8")
    return log_file, rotated_file


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    logger_module._initialized = False

    yield

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    for handler in original_handlers:
        root.addHandler(handler)

    root.setLevel(original_level)
    logger_module._initialized = False


def test_setup_logging_creates_startup_log_file(tmp_path):
    logger_module.setup_logging(log_dir=str(tmp_path), force=True)

    file_handler = _get_file_handler()
    log_file = Path(file_handler.baseFilename)

    assert log_file.parent == tmp_path
    assert re.fullmatch(r"app-\d{8}-\d{6}-\d{6}\.log", log_file.name)
    assert not (tmp_path / "app.log").exists()


def test_setup_logging_force_creates_new_log_file(tmp_path):
    logger_module.setup_logging(log_dir=str(tmp_path), force=True)
    first_log_file = Path(_get_file_handler().baseFilename)

    time.sleep(0.001)
    logger_module.setup_logging(log_dir=str(tmp_path), force=True)
    second_log_file = Path(_get_file_handler().baseFilename)

    assert second_log_file != first_log_file
    assert first_log_file.exists()
    assert second_log_file.exists()


def test_log_records_are_written_to_current_startup_log(tmp_path):
    logger_module.setup_logging(log_dir=str(tmp_path), force=True)

    logger = logger_module.get_logger("tests.logger")
    logger.info("startup-log-message")

    file_handler = _get_file_handler()
    file_handler.flush()

    log_file = Path(file_handler.baseFilename)
    assert "startup-log-message" in log_file.read_text(encoding="utf-8")


def test_setup_logging_keeps_latest_5_startup_log_groups(tmp_path):
    for index in range(6):
        _make_startup_log_files(tmp_path, index)

    preserved_file = tmp_path / "desktop.log"
    preserved_file.write_text("desktop", encoding="utf-8")

    logger_module.setup_logging(log_dir=str(tmp_path), force=True)

    remaining_groups = {
        match.group("base")
        for path in tmp_path.iterdir()
        if path.is_file() and (match := logger_module._STARTUP_LOG_FILE_RE.match(path.name))
    }

    assert len(remaining_groups) == 5
    assert "app-20240101-000000-000000.log" not in remaining_groups
    assert "app-20240101-000001-000000.log" not in remaining_groups
    assert not (tmp_path / "app-20240101-000000-000000.log").exists()
    assert not (tmp_path / "app-20240101-000000-000000.log.1").exists()
    assert not (tmp_path / "app-20240101-000001-000000.log").exists()
    assert not (tmp_path / "app-20240101-000001-000000.log.1").exists()
    assert preserved_file.exists()


def test_setup_logging_skips_locked_startup_log_files(tmp_path, monkeypatch):
    for index in range(6):
        _make_startup_log_files(tmp_path, index)

    locked_file = tmp_path / "app-20240101-000000-000000.log"
    original_unlink = Path.unlink

    def fake_unlink(path: Path, *args, **kwargs):
        if path == locked_file:
            raise PermissionError("file is locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    logger_module.setup_logging(log_dir=str(tmp_path), force=True)

    assert locked_file.exists()
    assert not (tmp_path / "app-20240101-000000-000000.log.1").exists()
