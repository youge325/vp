"""Canonical video metadata fixtures for planning and streaming tests."""

from __future__ import annotations

from app.ports.media import VideoMetadata


def make_video_metadata(
    source_frames: int,
    *,
    duration: float,
    width: int = 320,
    height: int = 180,
    source_fps: float = 24.0,
    has_audio: bool = True,
) -> VideoMetadata:
    return VideoMetadata(
        width=width,
        height=height,
        source_fps=source_fps,
        source_frames=source_frames,
        duration=duration,
        has_audio=has_audio,
    )


__all__ = ["make_video_metadata"]
