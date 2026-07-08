from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.encoder_segment_writer import EncoderSegmentWriter
from app.processing.streaming.metrics import PipelineMetrics


class _FakeWriter:
    def __init__(self, output_path: str, progress_callback: Any = None) -> None:
        self.output_path = output_path
        self.progress_callback = progress_callback
        self.frames: list[np.ndarray] = []
        self.output_frame_count = 0
        self.closed = False

    def write_frame(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def close(self) -> None:
        self.closed = True
        output = Path(self.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"segment")
        self.output_frame_count = len(self.frames)
        if self.progress_callback is not None:
            self.progress_callback(
                {
                    "frame": self.output_frame_count,
                    "fps": 24.0,
                    "speed": 1.0,
                    "out_time_seconds": None,
                    "progress": "end",
                }
            )


class _FakeFFmpeg:
    def __init__(self) -> None:
        self.writers: list[_FakeWriter] = []

    def open_rawvideo_encoder(self, *, output_path: str, progress_callback: Any = None, **kwargs: Any) -> _FakeWriter:
        del kwargs
        writer = _FakeWriter(output_path, progress_callback=progress_callback)
        self.writers.append(writer)
        return writer

    def get_frame_count(self, _path: str) -> int:
        return 0


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _segment_writer(
    tmp_path: Path, ffmpeg: _FakeFFmpeg, progress_events: list[tuple[int, str]]
) -> EncoderSegmentWriter:
    return EncoderSegmentWriter(
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        encode_config={"container": "mp4"},
        manifest=SegmentManifest(str(tmp_path / "out.mp4")),
        width=1,
        height=1,
        fps=24.0,
        output_fps=None,
        segment_frames=2,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        output_path=str(tmp_path / "out.mp4"),
        encode_progress_callback=lambda frame, _fps, _speed, _time, progress: progress_events.append((frame, progress)),
        metrics=PipelineMetrics(),
    )


def test_encoder_segment_writer_seals_ready_segment_and_finalizes_manifest(tmp_path: Path) -> None:
    ffmpeg = _FakeFFmpeg()
    progress_events: list[tuple[int, str]] = []
    writer = _segment_writer(tmp_path, ffmpeg, progress_events)

    writer.write_frame(_frame(10))
    assert writer.seal_if_ready(next_source_frame=1) is False
    writer.write_frame(_frame(20))
    assert writer.seal_if_ready(next_source_frame=2) is True

    segments = writer.manifest.scan_completed_chunks()
    assert [segment.frame_count for segment in segments] == [2]
    assert [segment.next_source_frame for segment in segments] == [2]
    assert ffmpeg.writers[0].closed is True
    assert progress_events == [(2, "end")]
    assert writer.metrics.snapshot()["processedFrames"] == 2


def test_encoder_segment_writer_discards_open_segment_on_cleanup(tmp_path: Path) -> None:
    ffmpeg = _FakeFFmpeg()
    writer = _segment_writer(tmp_path, ffmpeg, [])

    writer.write_frame(_frame(10))
    tmp_path_written = Path(ffmpeg.writers[0].output_path)
    writer.discard_open_segment()

    assert ffmpeg.writers[0].closed is True
    assert not tmp_path_written.exists()
    assert writer.manifest.scan_completed_chunks() == []
