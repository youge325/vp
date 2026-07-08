"""Small segment helper rules shared by encoder runtimes."""

from __future__ import annotations

from typing import Any, Callable

from app.utils.ffmpeg import FFmpegWrapper


def make_segment_progress_callback(
    segment_start_frame: int,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> Callable[[dict[str, Any]], None] | None:
    if encode_progress_callback is None:
        return None

    def callback(progress: dict[str, Any]) -> None:
        encode_progress_callback(
            segment_start_frame + int(progress.get("frame") or 0),
            progress.get("fps"),
            progress.get("speed"),
            progress.get("out_time_seconds"),
            str(progress.get("progress") or ""),
        )

    return callback


def resolve_segment_output_frame_count(
    ffmpeg: FFmpegWrapper,
    writer: Any,
    segment_path: str,
    *,
    fallback_frame_count: int,
) -> int:
    output_frame_count = int(getattr(writer, "output_frame_count", 0) or 0)
    if output_frame_count > 0:
        return output_frame_count
    return ffmpeg.get_frame_count(segment_path) or fallback_frame_count


__all__ = ["make_segment_progress_callback", "resolve_segment_output_frame_count"]
