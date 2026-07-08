from __future__ import annotations

from app.processing.streaming.encoder_segments import (
    make_segment_progress_callback,
    resolve_segment_output_frame_count,
)


class _FakeWriter:
    def __init__(self, output_frame_count: int) -> None:
        self.output_frame_count = output_frame_count


class _FakeFFmpeg:
    def __init__(self, frame_count: int | None) -> None:
        self.frame_count = frame_count
        self.counted_path: str | None = None

    def get_frame_count(self, path: str) -> int | None:
        self.counted_path = path
        return self.frame_count


def test_make_segment_progress_callback_offsets_frame_numbers() -> None:
    calls: list[tuple[int, float | None, float | None, float | None, str]] = []
    callback = make_segment_progress_callback(10, lambda *args: calls.append(args))

    assert callback is not None
    callback({"frame": "3", "fps": 48.0, "speed": 1.25, "out_time_seconds": 2.5, "progress": "continue"})

    assert calls == [(13, 48.0, 1.25, 2.5, "continue")]


def test_make_segment_progress_callback_returns_none_without_consumer() -> None:
    assert make_segment_progress_callback(10, None) is None


def test_resolve_segment_output_frame_count_prefers_writer_counter() -> None:
    ffmpeg = _FakeFFmpeg(frame_count=9)

    result = resolve_segment_output_frame_count(
        ffmpeg,
        _FakeWriter(output_frame_count=4),
        "segment.mp4",
        fallback_frame_count=2,
    )

    assert result == 4
    assert ffmpeg.counted_path is None


def test_resolve_segment_output_frame_count_falls_back_to_probe_then_written_count() -> None:
    probed = resolve_segment_output_frame_count(
        _FakeFFmpeg(frame_count=6),
        _FakeWriter(output_frame_count=0),
        "segment.mp4",
        fallback_frame_count=2,
    )
    fallback = resolve_segment_output_frame_count(
        _FakeFFmpeg(frame_count=0),
        _FakeWriter(output_frame_count=0),
        "segment.mp4",
        fallback_frame_count=2,
    )

    assert probed == 6
    assert fallback == 2
