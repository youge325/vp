"""Filesystem helpers for the video processing backend."""

from __future__ import annotations

import os

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
