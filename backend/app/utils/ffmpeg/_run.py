"""Shared FFmpeg subprocess invocation helper.

Encode, media-probe, and capability-probe paths share this helper so timeout,
encoding, and hidden-window behaviour cannot drift.
"""

from __future__ import annotations

import subprocess

from app.utils.logger import get_logger
from app.utils.subprocess_utils import hidden_subprocess_kwargs

logger = get_logger(__name__)


def run_ffmpeg_command(
    cmd: list[str],
    *,
    timeout: int = 3600,
) -> subprocess.CompletedProcess[str]:
    """Run an ffmpeg / ffprobe command and raise on non-zero exit.

    The single public entry point for synchronous ffmpeg invocations
    inside the backend. ``stderr`` is preferred when the command fails;
    falls back to ``stdout`` to keep the error message non-empty.
    """
    logger.debug("Running FFmpeg command: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **hidden_subprocess_kwargs(),
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"FFmpeg command failed ({result.returncode}): {message}")
    return result


__all__ = ["run_ffmpeg_command"]
