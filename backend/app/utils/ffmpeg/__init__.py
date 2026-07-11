"""Production FFmpeg facade over focused probing, I/O, and encoding modules."""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable

from app.config import settings
from app.utils.logger import get_logger

from . import capabilities as _capabilities
from . import encode as _encode
from . import media_probe as _media_probe
from .io import (
    RawVideoReader as _RawVideoReader,
    RawVideoWriter as _RawVideoWriter,
    open_rawvideo_decoder as _open_rawvideo_decoder,
    open_rawvideo_encoder as _open_rawvideo_encoder,
)

logger = get_logger(__name__)

__all__ = ["FFmpegWrapper"]


class FFmpegWrapper:
    """Wrap FFmpeg/FFprobe calls and normalize runtime capabilities."""

    def __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None):
        self._ffmpeg_path_explicit = ffmpeg_path is not None
        self._ffprobe_path_explicit = ffprobe_path is not None
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH
        self.ffprobe_path = ffprobe_path or settings.FFPROBE_PATH
        self._auto_detect_paths()
        # Probe caches keyed by (abspath, mtime_ns, size); invalidates on
        # file mutation. Phase C.1.4 added ``size`` because some build tools
        # preserve mtime when copying — without it a content swap would
        # silently return stale probe info.
        self._video_info_cache: dict[tuple[str, int, int], dict[str, Any]] = {}
        self._frame_count_cache: dict[tuple[str, int, int], int] = {}

    # ------------------------------------------------------------------ #
    #  Path helpers
    # ------------------------------------------------------------------ #

    def _auto_detect_paths(self) -> None:
        if not self._ffmpeg_path_explicit and not os.path.isfile(self.ffmpeg_path):
            found = shutil.which("ffmpeg")
            if found:
                logger.info("Auto-detected ffmpeg at %s", found)
                self.ffmpeg_path = found

        if not self._ffprobe_path_explicit and not os.path.isfile(self.ffprobe_path):
            found = shutil.which("ffprobe")
            if found:
                logger.info("Auto-detected ffprobe at %s", found)
                self.ffprobe_path = found

    # ------------------------------------------------------------------ #
    #  Media metadata
    # ------------------------------------------------------------------ #

    def get_video_info(self, input_path: str) -> dict[str, Any]:
        return _media_probe.get_video_info(self.ffprobe_path, input_path, self._video_info_cache)

    def get_fps(self, input_path: str) -> float:
        info = self.get_video_info(input_path)
        return _media_probe.get_fps(info)

    def get_frame_count(self, input_path: str) -> int:
        info = self.get_video_info(input_path)
        duration = _media_probe.get_duration(info)
        fps = _media_probe.get_fps(info)
        return _media_probe.get_frame_count(
            self.ffprobe_path,
            input_path,
            info,
            duration,
            fps,
            self._frame_count_cache,
        )

    def get_duration(self, input_path: str) -> float:
        info = self.get_video_info(input_path)
        return _media_probe.get_duration(info)

    def has_audio(self, input_path: str) -> bool:
        info = self.get_video_info(input_path)
        return _media_probe.has_audio(info)

    def get_primary_video_codec(self, input_path: str) -> str:
        info = self.get_video_info(input_path)
        return _media_probe.get_primary_video_codec(info)

    # ------------------------------------------------------------------ #
    #  Raw video I/O (delegate to io.py)
    # ------------------------------------------------------------------ #

    def open_rawvideo_decoder(
        self,
        *,
        input_path: str,
        width: int,
        height: int,
        decode_config: dict[str, Any] | None = None,
        start_frame: int = 0,
        frame_count: int | None = None,
    ) -> _RawVideoReader:
        decode_input_args = _encode.build_decode_input_args(input_path, decode_config)
        return _open_rawvideo_decoder(
            self.ffmpeg_path,
            width=width,
            height=height,
            decode_input_args=decode_input_args,
            start_frame=start_frame,
            frame_count=frame_count,
        )

    def open_rawvideo_encoder(
        self,
        *,
        output_path: str,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        encode_config: dict[str, Any] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> _RawVideoWriter:
        encode_output_args = _encode.build_encode_output_args(output_path, encode_config)
        return _open_rawvideo_encoder(
            self.ffmpeg_path,
            width=width,
            height=height,
            fps=fps,
            output_fps=output_fps,
            encode_output_args=encode_output_args,
            progress_callback=progress_callback,
        )

    # ------------------------------------------------------------------ #
    #  Encoding / processing (delegate to encode.py)
    # ------------------------------------------------------------------ #

    def extract_audio(self, input_path: str, output_path: str) -> str | None:
        return _encode.extract_audio(self.ffmpeg_path, input_path, output_path)

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        return _encode.merge_audio(self.ffmpeg_path, video_path, audio_path, output_path)

    def concat_videos(self, segment_paths: list[str], output_path: str) -> str:
        return _encode.concat_videos(self.ffmpeg_path, segment_paths, output_path)

    def transcode_video(
        self,
        *,
        input_path: str,
        output_path: str,
        decode_config: dict[str, Any] | None = None,
        encode_config: dict[str, Any] | None = None,
        output_fps: float | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        encode_config = encode_config or {}
        keep_audio = bool(encode_config.get("keepAudio", True))
        decode_input_args = _encode.build_decode_input_args(input_path, decode_config)
        encode_output_args = _encode.build_encode_output_args(output_path, encode_config)
        return _encode.transcode_video(
            self.ffmpeg_path,
            output_path=output_path,
            decode_input_args=decode_input_args,
            encode_output_args=encode_output_args,
            output_fps=output_fps,
            progress_callback=progress_callback,
            keep_audio=keep_audio,
        )

    # ------------------------------------------------------------------ #
    #  Capability discovery
    # ------------------------------------------------------------------ #

    def discover_capabilities(self, gpu_adapters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return _capabilities.discover_capabilities(self.ffmpeg_path, gpu_adapters)

    # ------------------------------------------------------------------ #
    #  Availability
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        return _media_probe.is_available(self.ffmpeg_path)
