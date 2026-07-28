from __future__ import annotations

from app.processing.streaming.encoder_segments import resolve_segment_output_frame_count
from tests.support.frame_count_probe import FakeFrameCountProbe


class _FakeWriter:
    def __init__(self, output_frame_count: int) -> None:
        self.output_frame_count = output_frame_count


def test_resolve_segment_output_frame_count_prefers_writer_counter() -> None:
    ffmpeg = FakeFrameCountProbe(frame_count=9)

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
        FakeFrameCountProbe(frame_count=6),
        _FakeWriter(output_frame_count=0),
        "segment.mp4",
        fallback_frame_count=2,
    )
    fallback = resolve_segment_output_frame_count(
        FakeFrameCountProbe(frame_count=0),
        _FakeWriter(output_frame_count=0),
        "segment.mp4",
        fallback_frame_count=2,
    )

    assert probed == 6
    assert fallback == 2
