"""Filesystem helpers for the video processing backend."""

from __future__ import annotations

import os
import shutil
import tempfile

from app.utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {
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


def create_temp_dir(base_dir: str | None = None, prefix: str = "vp_") -> str:
    if base_dir:
        os.makedirs(base_dir, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix=prefix, dir=base_dir)
    else:
        temp_dir = tempfile.mkdtemp(prefix=prefix)
    logger.info("Created temp directory %s", temp_dir)
    return temp_dir


def cleanup_dir(dir_path: str) -> None:
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
        logger.info("Cleaned directory %s", dir_path)


def validate_input_path(input_path: str) -> bool:
    if not os.path.isfile(input_path):
        return False
    _, ext = os.path.splitext(input_path)
    return ext.lower() in SUPPORTED_EXTENSIONS


def get_output_path(
    input_path: str,
    output_dir: str,
    suffix: str = "_processed",
    extension: str = ".mp4",
) -> str:
    basename = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(output_dir, exist_ok=True)
    resolved_extension = extension if extension.startswith(".") else f".{extension}"
    return os.path.join(output_dir, f"{basename}{suffix}{resolved_extension}")


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
