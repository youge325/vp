"""Consumer-owned media ports for planning and streaming."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

import numpy as np

ConfigMap = Mapping[str, object]
EncodeProgressCallback = Callable[[int, float | None, float | None, float | None, str], None]


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Canonical metadata needed by planning; raw ffprobe JSON stays in the adapter."""

    width: int
    height: int
    source_fps: float
    source_frames: int
    duration: float
    has_audio: bool


@dataclass(frozen=True, slots=True)
class VideoInspection:
    """Small metadata projection consumed only by the ``info`` command."""

    fps: float
    width: int
    height: int
    video_codec: str


class RawVideoReaderPort(Protocol):
    def read_frame(self) -> np.ndarray | None: ...

    def close(self) -> None: ...

    def terminate_and_reap(self, *, deadline: float) -> bool: ...


class RawVideoWriterPort(Protocol):
    @property
    def output_frame_count(self) -> int: ...

    def write_frame(self, frame: np.ndarray) -> None: ...

    def close(self) -> None: ...

    def terminate_and_reap(self, *, deadline: float) -> bool: ...


class MediaProbePort(Protocol):
    def probe_video(self, input_path: str) -> VideoMetadata: ...


class VideoInspectionPort(Protocol):
    def inspect_video(self, input_path: str) -> VideoInspection: ...


class FrameCountProbePort(Protocol):
    def get_frame_count(self, input_path: str) -> int: ...


class RawVideoPort(Protocol):
    def open_rawvideo_decoder(
        self,
        *,
        input_path: str,
        width: int,
        height: int,
        decode_config: ConfigMap | None = None,
        start_frame: int = 0,
        frame_count: int | None = None,
    ) -> RawVideoReaderPort: ...


class _EncodePort(Protocol):
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
    ) -> RawVideoWriterPort: ...

    def transcode_video(
        self,
        *,
        input_path: str,
        output_path: str,
        decode_config: ConfigMap | None = None,
        encode_config: ConfigMap | None = None,
        output_fps: float | None = None,
        progress_callback: EncodeProgressCallback | None = None,
    ) -> None: ...


class _FinalizationPort(Protocol):
    def concat_videos(self, inputs: list[str], output_path: str) -> None: ...

    def extract_audio(self, input_path: str, output_path: str) -> bool: ...

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> None: ...


class EncodingMediaPort(FrameCountProbePort, _EncodePort, Protocol):
    """Operations consumed by the segmented encoder."""


class FinalizingMediaPort(_FinalizationPort, Protocol):
    """Operations consumed by output finalization."""


class StageFileMediaPort(RawVideoPort, EncodingMediaPort, Protocol):
    """Raw decoding and encoding consumed by file-backed stages."""


class MediaRuntimePort(
    MediaProbePort,
    RawVideoPort,
    EncodingMediaPort,
    _FinalizationPort,
    Protocol,
):
    """Composition-root aggregate; leaf consumers use narrower ports."""


__all__ = [
    "ConfigMap",
    "EncodeProgressCallback",
    "EncodingMediaPort",
    "FinalizingMediaPort",
    "FrameCountProbePort",
    "MediaProbePort",
    "MediaRuntimePort",
    "RawVideoPort",
    "RawVideoReaderPort",
    "RawVideoWriterPort",
    "StageFileMediaPort",
    "VideoInspection",
    "VideoInspectionPort",
    "VideoMetadata",
]
