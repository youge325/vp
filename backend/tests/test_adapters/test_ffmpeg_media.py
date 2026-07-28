from __future__ import annotations

from typing import Any, cast

from app.adapters import FFmpegMediaAdapter
from app.ports.media import VideoMetadata
from app.utils.ffmpeg import FFmpegWrapper


class _Writer:
    output_frame_count = 0

    def write_frame(self, _frame) -> None:
        return None

    def close(self) -> None:
        return None


class _FakeFFmpeg:
    def __init__(self) -> None:
        self.encoder_progress_callback = None

    def get_video_info(self, _input_path: str) -> dict[str, object]:
        return {"streams": [{"codec_type": "video", "width": 320, "height": 180}]}

    def get_fps(self, _input_path: str) -> float:
        return 24.0

    def get_frame_count(self, _input_path: str) -> int:
        return 48

    def get_duration(self, _input_path: str) -> float:
        return 2.0

    def has_audio(self, _input_path: str) -> bool:
        return True

    def open_rawvideo_encoder(self, **kwargs: Any) -> _Writer:
        self.encoder_progress_callback = kwargs["progress_callback"]
        return _Writer()


def _adapter() -> tuple[FFmpegMediaAdapter, _FakeFFmpeg]:
    ffmpeg = _FakeFFmpeg()
    return FFmpegMediaAdapter(cast(FFmpegWrapper, ffmpeg)), ffmpeg


def test_probe_video_hides_raw_ffprobe_shape_behind_metadata() -> None:
    adapter, _ffmpeg = _adapter()

    assert adapter.probe_video("input.mp4") == VideoMetadata(
        width=320,
        height=180,
        source_fps=24.0,
        source_frames=48,
        duration=2.0,
        has_audio=True,
    )


def test_encoder_progress_is_translated_at_the_adapter_boundary() -> None:
    adapter, ffmpeg = _adapter()
    events: list[tuple[int, float | None, float | None, float | None, str]] = []

    adapter.open_rawvideo_encoder(
        output_path="chunk.mp4",
        width=320,
        height=180,
        fps=24.0,
        progress_callback=lambda *event: events.append(event),
        progress_frame_offset=100,
    )
    assert ffmpeg.encoder_progress_callback is not None
    ffmpeg.encoder_progress_callback(
        {
            "frame": 25,
            "fps": 24.0,
            "speed": 1.5,
            "out_time_seconds": 1.0,
            "progress": "continue",
        }
    )

    assert events == [(125, 24.0, 1.5, 1.0, "continue")]
