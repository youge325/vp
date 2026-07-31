"""FFmpeg implementation of the backend's consumer-owned media ports."""

from __future__ import annotations

from app.ports.media import (
    ConfigMap,
    EncodeProgressCallback,
    RawVideoReaderPort,
    RawVideoWriterPort,
    VideoMetadata,
)
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.ffmpeg._progress import make_encode_progress_callback
from app.utils.ffmpeg.media_probe import get_primary_video_dimensions


class FFmpegMediaAdapter:
    """Translate neutral media operations to the concrete FFmpeg facade."""

    def __init__(self, ffmpeg: FFmpegWrapper) -> None:
        self._ffmpeg = ffmpeg

    def probe_video(self, input_path: str) -> VideoMetadata:
        raw_info = self._ffmpeg.get_video_info(input_path)
        width, height = get_primary_video_dimensions(raw_info)
        return VideoMetadata(
            width=width,
            height=height,
            source_fps=self._ffmpeg.get_fps(input_path),
            source_frames=self._ffmpeg.get_frame_count(input_path),
            duration=self._ffmpeg.get_duration(input_path),
            has_audio=self._ffmpeg.has_audio(input_path),
        )

    def get_frame_count(self, input_path: str) -> int:
        return self._ffmpeg.get_frame_count(input_path)

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
        return self._ffmpeg.open_rawvideo_decoder(
            input_path=input_path,
            width=width,
            height=height,
            decode_config=dict(decode_config) if decode_config is not None else None,
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
        return self._ffmpeg.open_rawvideo_encoder(
            output_path=output_path,
            width=width,
            height=height,
            fps=fps,
            output_fps=output_fps,
            encode_config=dict(encode_config) if encode_config is not None else None,
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
        self._ffmpeg.transcode_video(
            input_path=input_path,
            output_path=output_path,
            decode_config=dict(decode_config) if decode_config is not None else None,
            encode_config=dict(encode_config) if encode_config is not None else None,
            output_fps=output_fps,
            progress_callback=make_encode_progress_callback(progress_callback),
        )

    def concat_videos(self, inputs: list[str], output_path: str) -> None:
        self._ffmpeg.concat_videos(inputs, output_path)

    def extract_audio(self, input_path: str, output_path: str) -> bool:
        return self._ffmpeg.extract_audio(input_path, output_path)

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> None:
        self._ffmpeg.merge_audio(video_path, audio_path, output_path)


__all__ = ["FFmpegMediaAdapter"]
