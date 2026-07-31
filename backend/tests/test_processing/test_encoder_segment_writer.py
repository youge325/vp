from __future__ import annotations

from pathlib import Path

import pytest

from app.planning.manifest import ResumeState, SegmentManifest
from tests.support.streaming_runtime import create_test_manifest
from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_segment_writer import EncoderSegmentWriter, EncoderWriterOwner
from app.processing.streaming.metrics import PipelineMetrics
from tests.support.raw_video import FakeRawVideoMedia, frame as _frame


def _segment_writer(
    tmp_path: Path, ffmpeg: FakeRawVideoMedia, progress_events: list[tuple[int, str]]
) -> tuple[EncoderSegmentWriter, SegmentManifest, PipelineMetrics, EncoderWriterOwner]:
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))
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
    owner = EncoderWriterOwner()
    return EncoderSegmentWriter(config, owner), manifest, metrics, owner


def test_encoder_segment_writer_seals_ready_segment_and_finalizes_manifest(tmp_path: Path) -> None:
    ffmpeg = FakeRawVideoMedia()
    progress_events: list[tuple[int, str]] = []
    writer, manifest, metrics, _owner = _segment_writer(tmp_path, ffmpeg, progress_events)

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
    writer, manifest, _metrics, _owner = _segment_writer(tmp_path, ffmpeg, [])

    writer.write_frame(_frame(10))
    tmp_path_written = Path(ffmpeg.writers[0].output_path)
    writer.discard_open_segment()

    assert ffmpeg.writers[0].closed is True
    assert not tmp_path_written.exists()
    assert manifest.scan_completed_chunks() == []


def test_encoder_segment_writer_retains_failed_close_for_owner_reap(tmp_path: Path) -> None:
    ffmpeg = FakeRawVideoMedia()
    writer, _manifest, _metrics, owner = _segment_writer(tmp_path, ffmpeg, [])
    writer.write_frame(_frame(10))
    assert ffmpeg.writer is not None
    terminate_calls = 0

    def fail_close() -> None:
        raise RuntimeError("close deadline exceeded")

    def terminate_and_reap(*, deadline: float) -> bool:
        nonlocal terminate_calls
        assert deadline >= 0
        terminate_calls += 1
        return True

    ffmpeg.writer.close = fail_close
    ffmpeg.writer.terminate_and_reap = terminate_and_reap

    with pytest.raises(RuntimeError, match="close deadline"):
        writer.discard_open_segment()

    assert owner.terminate_and_reap(deadline=1.0) is True
    assert terminate_calls == 1
