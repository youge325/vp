"""Shared frame-count probe double."""

from __future__ import annotations


class FakeFrameCountProbe:
    def __init__(self, frame_count: int | None) -> None:
        self.frame_count = frame_count
        self.counted_path: str | None = None

    def get_frame_count(self, path: str) -> int | None:
        self.counted_path = path
        return self.frame_count
