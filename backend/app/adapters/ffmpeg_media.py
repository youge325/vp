"""Direct FFmpeg implementation of consumer-owned media ports."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.ports.media import (
    ConfigMap,
    EncodeProgressCallback,
    RawVideoReaderPort,
    RawVideoWriterPort,
    VideoInspection,
    VideoMetadata,
)
from app.utils.ffmpeg import encode as _encode
from app.utils.ffmpeg import media_probe as _media_probe
from app.utils.ffmpeg._progress import make_encode_progress_callback
from app.utils.ffmpeg.io import (
    open_rawvideo_decoder as _open_rawvideo_decoder,
    open_rawvideo_encoder as _open_rawvideo_encoder,
)


_ProbeFingerprint = tuple[str, int, int]


@dataclass(frozen=True, slots=True)
class _ProbeSnapshot:
    fingerprint: _ProbeFingerprint
    raw_info: dict[str, Any]
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    video_codec: str


class FFmpegMediaAdapter:
    """Own resolved executable paths, probe caches, and concrete FFmpeg calls."""

    def __init__(self, ffmpeg_path: str, ffprobe_path: str) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = ffprobe_path
        self._snapshot_cache: dict[_ProbeFingerprint, _ProbeSnapshot] = {}
        self._frame_count_cache: dict[_ProbeFingerprint, int] = {}

    @staticmethod
    def _fingerprint(input_path: str) -> _ProbeFingerprint:
        normalized_path = os.path.normcase(os.path.abspath(input_path))
        try:
            stat = os.stat(normalized_path)
        except OSError:
            return normalized_path, -1, -1
        return normalized_path, stat.st_mtime_ns, stat.st_size

    def _snapshot(self, input_path: str) -> _ProbeSnapshot:
        fingerprint = self._fingerprint(input_path)
        cached = self._snapshot_cache.get(fingerprint)
        if cached is not None:
            return cached

        raw_info = _media_probe.probe_video_info(self._ffprobe_path, input_path)
        width, height = _media_probe.get_primary_video_dimensions(raw_info)
        snapshot = _ProbeSnapshot(
            fingerprint=fingerprint,
            raw_info=raw_info,
            width=width,
            height=height,
            fps=_media_probe.get_fps(raw_info),
            duration=_media_probe.get_duration(raw_info),
            has_audio=_media_probe.has_audio(raw_info),
            video_codec=_media_probe.get_primary_video_codec(raw_info),
        )
        self._snapshot_cache[fingerprint] = snapshot
        return snapshot

    def _frame_count(self, input_path: str, snapshot: _ProbeSnapshot) -> int:
        cached = self._frame_count_cache.get(snapshot.fingerprint)
        if cached is not None:
            return cached
        frame_count = _media_probe.probe_frame_count(
            self._ffprobe_path,
            input_path,
            snapshot.raw_info,
            snapshot.duration,
            snapshot.fps,
        )
        self._frame_count_cache[snapshot.fingerprint] = frame_count
        return frame_count

    def probe_video(self, input_path: str) -> VideoMetadata:
        snapshot = self._snapshot(input_path)
        return VideoMetadata(
            width=snapshot.width,
            height=snapshot.height,
            source_fps=snapshot.fps,
            source_frames=self._frame_count(input_path, snapshot),
            duration=snapshot.duration,
            has_audio=snapshot.has_audio,
        )

    def inspect_video(self, input_path: str) -> VideoInspection:
        snapshot = self._snapshot(input_path)
        return VideoInspection(
            fps=snapshot.fps,
            width=snapshot.width,
            height=snapshot.height,
            video_codec=snapshot.video_codec,
        )

    def get_frame_count(self, input_path: str) -> int:
        snapshot = self._snapshot(input_path)
        return self._frame_count(input_path, snapshot)

    def open_rawvideo_decoder(
        self,
        *,
        input_path: str,
        width: int,
        height: int,
        decode_config: ConfigMap | None = None,
        start_frame: int = 0,
        frame_count: int | None = None,
    ) -> RawVideoReaderPort:
        decode_input_args = _encode.build_decode_input_args(
            input_path,
            dict(decode_config) if decode_config is not None else None,
        )
        return _open_rawvideo_decoder(
            self._ffmpeg_path,
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
        encode_config: ConfigMap | None = None,
        progress_callback: EncodeProgressCallback | None = None,
        progress_frame_offset: int = 0,
    ) -> RawVideoWriterPort:
        encode_output_args = _encode.build_encode_output_args(
            output_path,
            dict(encode_config) if encode_config is not None else None,
        )
        return _open_rawvideo_encoder(
            self._ffmpeg_path,
            width=width,
            height=height,
            fps=fps,
            output_fps=output_fps,
            encode_output_args=encode_output_args,
            progress_callback=make_encode_progress_callback(
                progress_callback,
                frame_offset=progress_frame_offset,
            ),
        )

    def transcode_video(
        self,
        *,
        input_path: str,
        output_path: str,
        decode_config: ConfigMap | None = None,
        encode_config: ConfigMap | None = None,
        output_fps: float | None = None,
        progress_callback: EncodeProgressCallback | None = None,
    ) -> None:
        concrete_encode_config = dict(encode_config) if encode_config is not None else {}
        _encode.transcode_video(
            self._ffmpeg_path,
            decode_input_args=_encode.build_decode_input_args(
                input_path,
                dict(decode_config) if decode_config is not None else None,
            ),
            encode_output_args=_encode.build_encode_output_args(output_path, concrete_encode_config),
            output_fps=output_fps,
            progress_callback=make_encode_progress_callback(progress_callback),
            keep_audio=bool(concrete_encode_config.get("keepAudio", True)),
        )

    def concat_videos(self, inputs: list[str], output_path: str) -> None:
        _encode.concat_videos(self._ffmpeg_path, inputs, output_path)

    def extract_audio(self, input_path: str, output_path: str) -> bool:
        return _encode.extract_audio(self._ffmpeg_path, input_path, output_path)

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> None:
        _encode.merge_audio(self._ffmpeg_path, video_path, audio_path, output_path)


__all__ = ["FFmpegMediaAdapter"]
