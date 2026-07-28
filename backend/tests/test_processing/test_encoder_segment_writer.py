from __future__ import annotations

from pathlib import Path

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_segment_writer import EncoderSegmentWriter
from app.processing.streaming.metrics import PipelineMetrics
from tests.support.raw_video import FakeRawVideoMedia, frame as _frame


def _segment_writer(
    tmp_path: Path, ffmpeg: FakeRawVideoMedia, progress_events: list[tuple[int, str]]
) -> tuple[EncoderSegmentWriter, SegmentManifest, PipelineMetrics]:
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    metrics = PipelineMetrics()
    config = EncoderRuntimeConfig(
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        encode_config={"container": "mp4"},
        manifest=manifest,
        width=1,
        height=1,
        fps=24.0,
        output_fps=None,
        segment_frames=2,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        output_path=str(tmp_path / "out.mp4"),
        encode_progress_callback=lambda frame, _fps, _speed, _time, progress: progress_events.append((frame, progress)),
        metrics=metrics,
    )
    return EncoderSegmentWriter(config), manifest, metrics


def test_encoder_segment_writer_seals_ready_segment_and_finalizes_manifest(tmp_path: Path) -> None:
    ffmpeg = FakeRawVideoMedia()
    progress_events: list[tuple[int, str]] = []
    writer, manifest, metrics = _segment_writer(tmp_path, ffmpeg, progress_events)

    writer.write_frame(_frame(10))
    writer.seal_if_ready(next_source_frame=1)
    writer.write_frame(_frame(20))
    writer.seal_if_ready(next_source_frame=2)

    segments = manifest.scan_completed_chunks()
    assert [segment.frame_count for segment in segments] == [2]
    assert [segment.next_source_frame for segment in segments] == [2]
    assert ffmpeg.writers[0].closed is True
    assert progress_events == [(2, "end")]
    assert metrics.snapshot()["processedFrames"] == 2


def test_encoder_segment_writer_discards_open_segment_on_cleanup(tmp_path: Path) -> None:
    ffmpeg = FakeRawVideoMedia()
    writer, manifest, _metrics = _segment_writer(tmp_path, ffmpeg, [])

    writer.write_frame(_frame(10))
    tmp_path_written = Path(ffmpeg.writers[0].output_path)
    writer.discard_open_segment()

    assert ffmpeg.writers[0].closed is True
    assert not tmp_path_written.exists()
    assert manifest.scan_completed_chunks() == []
