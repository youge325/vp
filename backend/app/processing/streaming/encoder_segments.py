"""Small segment helper rules shared by encoder runtimes."""

from __future__ import annotations

from app.ports.media import FrameCountProbePort, RawVideoWriterPort


def resolve_segment_output_frame_count(
    ffmpeg: FrameCountProbePort,
    writer: RawVideoWriterPort,
    segment_path: str,
    *,
    fallback_frame_count: int,
) -> int:
    output_frame_count = int(writer.output_frame_count or 0)
    if output_frame_count > 0:
        return output_frame_count
    return ffmpeg.get_frame_count(segment_path) or fallback_frame_count


__all__ = ["resolve_segment_output_frame_count"]
