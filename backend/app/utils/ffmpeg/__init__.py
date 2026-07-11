"""FFmpeg command wrapper and capability probing.

Split into focused sub-modules: constants, progress parsing, I/O pipes,
probing, and encoding.  ``FFmpegWrapper`` remains the public face and
delegates to pure functions.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Callable

from app.config import settings
from app.utils.logger import get_logger

from . import _constants
from . import encode as _encode, probe as _probe
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
    #  Probing (delegate to probe.py)
    # ------------------------------------------------------------------ #

    def get_video_info(self, input_path: str) -> dict[str, Any]:
        return _probe.get_video_info(self.ffprobe_path, input_path, self._video_info_cache)

    def get_fps(self, input_path: str) -> float:
        info = self.get_video_info(input_path)
        return _probe.get_fps(info)

    def get_frame_count(self, input_path: str) -> int:
        info = self.get_video_info(input_path)
        duration = _probe.get_duration(info)
        fps = _probe.get_fps(info)
        return _probe.get_frame_count(self.ffprobe_path, input_path, info, duration, fps, self._frame_count_cache)

    def get_duration(self, input_path: str) -> float:
        info = self.get_video_info(input_path)
        return _probe.get_duration(info)

    def has_audio(self, input_path: str) -> bool:
        info = self.get_video_info(input_path)
        return _probe.has_audio(info)

    def get_primary_video_codec(self, input_path: str) -> str:
        info = self.get_video_info(input_path)
        return _probe.get_primary_video_codec(info)

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
        decode_input_args = self.build_decode_input_args(input_path, decode_config)
        return _open_rawvideo_decoder(
            self.ffmpeg_path,
            input_path=input_path,
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
        encode_output_args = self.build_encode_output_args(output_path, encode_config)
        return _open_rawvideo_encoder(
            self.ffmpeg_path,
            output_path=output_path,
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
        decode_input_args = self.build_decode_input_args(input_path, decode_config)
        encode_output_args = self.build_encode_output_args(output_path, encode_config)
        return _encode.transcode_video(
            self.ffmpeg_path,
            input_path=input_path,
            output_path=output_path,
            decode_input_args=decode_input_args,
            encode_output_args=encode_output_args,
            output_fps=output_fps,
            progress_callback=progress_callback,
            keep_audio=keep_audio,
        )

    # ------------------------------------------------------------------ #
    #  Capability discovery (delegate to probe.py)
    # ------------------------------------------------------------------ #

    def list_codec_names(self, mode: str) -> list[str]:
        return _probe.list_codec_names(self.ffmpeg_path, mode)

    def list_hwaccels(self) -> list[str]:
        return _probe.list_hwaccels(self.ffmpeg_path)

    def describe_codec(self, mode: str, name: str) -> str:
        return _probe.describe_codec(self.ffmpeg_path, mode, name)

    def parse_codec_profile(
        self,
        mode: str,
        metadata: dict[str, Any],
        help_text: str,
    ) -> dict[str, Any]:
        return _probe.parse_codec_profile(mode, metadata, help_text)

    def parse_avoptions(self, help_text: str) -> list[dict[str, Any]]:
        return _probe.parse_avoptions(help_text)

    def probe_rate_control_modes(self, codec: str, options: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _probe.probe_rate_control_modes(self.ffmpeg_path, codec, options)

    def probe_decoder_hardware_devices(
        self,
        decoder: str,
        codec: str,
        hardware_devices: list[str],
        hwaccels: list[str],
        encoder_names: set[str],
        probe_dir: str | None = None,
        sample_cache: dict[str, str | None] | None = None,
    ) -> list[str]:
        return _probe.probe_decoder_hardware_devices(
            self.ffmpeg_path,
            decoder,
            codec,
            hardware_devices,
            hwaccels,
            encoder_names,
            probe_dir=probe_dir,
            sample_cache=sample_cache,
        )

    def probe_decoder_hardware_device_options(
        self,
        decoder: str,
        codec: str,
        devices: list[str],
        encoder_names: set[str],
        probe_dir: str | None = None,
        sample_cache: dict[str, str | None] | None = None,
    ) -> dict[str, list[dict[str, str]]]:
        return _probe.probe_decoder_hardware_device_options(
            self.ffmpeg_path,
            decoder,
            codec,
            devices,
            encoder_names,
            probe_dir=probe_dir,
            sample_cache=sample_cache,
        )

    def discover_capabilities(self, gpu_adapters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Discover FFmpeg capabilities, using instance methods so callers can mock them in tests."""
        adapters = gpu_adapters or []
        available_vendors = {adapter.get("vendor") for adapter in adapters if adapter.get("device_type") != "virtual"}
        encoder_names = set(self.list_codec_names("encoders"))
        decoder_names = set(self.list_codec_names("decoders"))
        hwaccels = self.list_hwaccels()

        encoder_profiles: list[dict[str, Any]] = []
        for candidate in _constants.ENCODER_CANDIDATES:
            if candidate["name"] not in encoder_names:
                continue
            if candidate["family"] != "cpu" and candidate["family"] not in available_vendors:
                continue
            profile = _probe.parse_codec_profile(
                "encoder",
                candidate,
                self.describe_codec("encoder", candidate["name"]),
            )
            profile["rateControlModes"] = self.probe_rate_control_modes(profile["name"], profile["options"])
            encoder_profiles.append(profile)

        decoder_profiles: list[dict[str, Any]] = [
            {
                "name": "software",
                "label": "Software Decode",
                "family": "software",
                "codec": "any",
                "available": True,
                "hardwareDevices": [],
                "hardwareDeviceOptions": {},
                "options": [],
            }
        ]
        verified_hwaccels: list[str] = []
        decoder_sample_cache: dict[str, str | None] = {}
        with tempfile.TemporaryDirectory(prefix="vp-decoder-probe-") as decoder_probe_dir:
            for candidate in _constants.DECODER_CANDIDATES:
                if candidate["name"] not in decoder_names:
                    continue
                if candidate["family"] not in available_vendors:
                    continue
                profile = _probe.parse_codec_profile(
                    "decoder",
                    candidate,
                    self.describe_codec("decoder", candidate["name"]),
                )
                profile["hardwareDevices"] = self.probe_decoder_hardware_devices(
                    profile["name"],
                    profile["codec"],
                    profile["hardwareDevices"],
                    hwaccels,
                    encoder_names,
                    probe_dir=decoder_probe_dir,
                    sample_cache=decoder_sample_cache,
                )
                for device in profile["hardwareDevices"]:
                    if device not in verified_hwaccels:
                        verified_hwaccels.append(device)
                profile["hardwareDeviceOptions"] = self.probe_decoder_hardware_device_options(
                    profile["name"],
                    profile["codec"],
                    profile["hardwareDevices"],
                    encoder_names,
                    probe_dir=decoder_probe_dir,
                    sample_cache=decoder_sample_cache,
                )
                decoder_profiles.append(profile)

        return {
            "hwaccels": verified_hwaccels,
            "encoderProfiles": encoder_profiles,
            "decoderProfiles": decoder_profiles,
        }

    # ------------------------------------------------------------------ #
    #  Argument builders (delegate to encode.py)
    # ------------------------------------------------------------------ #

    def build_decode_input_args(self, input_path: str, decode_config: dict[str, Any] | None = None) -> list[str]:
        return _encode.build_decode_input_args(input_path, decode_config)

    def build_encode_output_args(self, output_path: str, encode_config: dict[str, Any] | None = None) -> list[str]:
        return _encode.build_encode_output_args(output_path, encode_config)

    # ------------------------------------------------------------------ #
    #  Availability (delegate to probe.py)
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        return _probe.is_available(self.ffmpeg_path)
