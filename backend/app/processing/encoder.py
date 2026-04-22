"""Encode filter that turns processed frames back into a video."""

from __future__ import annotations

import os
import shutil
from typing import Any

from app.processing.pipeline import Filter
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EncodeFilter(Filter):
    """Encode a frame directory and optionally merge the source audio."""

    def __init__(
        self,
        ffmpeg_wrapper: FFmpegWrapper | None = None,
        encode_config: dict[str, Any] | None = None,
    ) -> None:
        self._ffmpeg = ffmpeg_wrapper or FFmpegWrapper()
        self._encode_config = encode_config or {}

    def process(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        frame_dir = data.get("frame_dir")
        if not frame_dir or not os.path.isdir(frame_dir):
            raise FileNotFoundError(f"Frame directory was not found: {frame_dir}")

        output_path = data.get("output_path")
        if not output_path:
            output_dir = context.get("output_dir", os.path.join(os.path.dirname(__file__), "..", "..", "output"))
            os.makedirs(output_dir, exist_ok=True)
            task_id = context.get("task_id", "unknown")
            output_path = os.path.join(output_dir, f"{task_id}_output.mp4")

        fps = data.get("fps", 60.0)
        input_path = data.get("input_path", "")
        frame_prefix = data.get("frame_prefix", "frame_%06d.png")
        target_fps = context.get("target_fps")
        output_fps = target_fps if target_fps is not None else None

        keep_audio = bool(self._encode_config.get("keepAudio", True))
        container = str(self._encode_config.get("container") or "").strip().lstrip(".")
        temp_video = _derive_temp_video_path(output_path, container or "mp4")

        self._ffmpeg.encode_from_frames(
            frame_dir=frame_dir,
            output_path=temp_video,
            fps=fps,
            output_fps=output_fps,
            frame_prefix=frame_prefix,
            encode_config=self._encode_config,
        )

        audio_merged = False
        if keep_audio and input_path and os.path.isfile(input_path):
            temp_dir = os.path.dirname(frame_dir)
            temp_audio = os.path.join(temp_dir, "audio.aac")
            try:
                audio_path = self._ffmpeg.extract_audio(input_path, temp_audio)
                if audio_path and os.path.isfile(audio_path):
                    final_path = self._ffmpeg.merge_audio(temp_video, audio_path, output_path)
                    audio_merged = final_path == output_path
                    if os.path.isfile(temp_audio):
                        os.remove(temp_audio)
                    if os.path.isfile(temp_video) and temp_video != output_path:
                        os.remove(temp_video)
                elif os.path.isfile(temp_video):
                    shutil.move(temp_video, output_path)
            except Exception as exc:  # pragma: no cover - defensive boundary
                logger.warning("Audio merge failed: %s", exc)
                if os.path.isfile(temp_video):
                    shutil.move(temp_video, output_path)
        elif os.path.isfile(temp_video):
            shutil.move(temp_video, output_path)

        return {
            **data,
            "output_path": output_path,
            "audio_merged": audio_merged,
        }

    def get_name(self) -> str:
        return "Encode"


def _derive_temp_video_path(output_path: str, container: str) -> str:
    suffix = f".{container}" if container else ".mp4"
    base, ext = os.path.splitext(output_path)
    resolved_ext = ext or suffix
    return f"{base}_noaudio{resolved_ext}"
