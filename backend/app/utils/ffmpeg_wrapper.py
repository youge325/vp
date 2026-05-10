"""Backward-compatibility shim for the old ffmpeg_wrapper module.

All functionality has moved to ``app.utils.ffmpeg``.  Import from there
for new code.
"""

from app.utils.ffmpeg import FFmpegWrapper  # noqa: F401
from app.utils.ffmpeg._progress import _parse_progress_snapshot  # noqa: F401
