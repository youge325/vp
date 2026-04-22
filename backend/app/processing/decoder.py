"""Decode filter that expands a video into frame images."""

from __future__ import annotations

import os
from typing import Any

from app.processing.pipeline import Filter
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DecodeFilter(Filter):
    """Decode the input video into a temporary frame directory."""

    def __init__(
        self,
        ffmpeg_wrapper: FFmpegWrapper | None = None,
        decode_config: dict[str, Any] | None = None,
    ) -> None:
        self._ffmpeg = ffmpeg_wrapper or FFmpegWrapper()
        self._decode_config = decode_config or {}

    def process(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        input_path = data.get("input_path")
        if not input_path or not os.path.isfile(input_path):
            raise FileNotFoundError(f"Input video was not found: {input_path}")

        task_id = context.get("task_id", "unknown")
        temp_dir = context.get("temp_dir", os.path.join(os.path.dirname(__file__), "..", "..", "temp"))
        frame_dir = os.path.join(temp_dir, task_id, "frames")
        os.makedirs(frame_dir, exist_ok=True)

        fps = self._ffmpeg.get_fps(input_path)
        total_frames = self._ffmpeg.get_frame_count(input_path)
        self._ffmpeg.decode_to_frames(input_path, frame_dir, decode_config=self._decode_config)

        actual_frames = len([name for name in os.listdir(frame_dir) if name.endswith(".png")])
        result = {
            **data,
            "frame_dir": frame_dir,
            "frame_prefix": "frame_%06d.png",
            "total_frames": actual_frames or total_frames,
            "original_fps": fps,
        }
        if "fps" not in data:
            result["fps"] = fps

        context["frame_dir"] = frame_dir
        context["total_frames"] = result["total_frames"]
        context["original_fps"] = fps
        return result

    def get_name(self) -> str:
        return "Decode"
