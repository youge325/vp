from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_chunk_encoding import encode_stage_worker_output
from app.processing.streaming.worker_plans import StageChunkPlan
from tests.support.raw_video import (
    FakeRawVideoMedia,
    frame as _frame,
    make_stage_file_runtime_config as _runtime_config,
)


def test_encode_stage_worker_output_skips_duplicate_frames_and_counts_encoded_frames(tmp_path: Path) -> None:
    chunk = StageChunkPlan(
        input_start_frame=2,
        input_frame_count=3,
        logical_input_frame_count=3,
        raw_output_frame_count=3,
        written_output_frame_count=2,
        skip_output_frames=1,
    )
    stdout = BytesIO(b"".join(np.ascontiguousarray(_frame(value)).tobytes() for value in (1, 2, 3)))
    ffmpeg = FakeRawVideoMedia(payload=b"encoded")
    metrics = PipelineMetrics()
    output_path = tmp_path / "chunk.mp4"

    encoded_frames = encode_stage_worker_output(
        config=_runtime_config(ffmpeg, metrics),
        output_path=str(output_path),
        worker_stdout=stdout,
        chunk=chunk,
    )

    assert encoded_frames == 2
    assert output_path.read_bytes() == b"encoded"
    assert ffmpeg.writer is not None
    assert ffmpeg.writer.closed is True
    assert [int(frame[0, 0, 0]) for frame in ffmpeg.writer.frames] == [2, 3]
    assert metrics.snapshot()["processedFrames"] == 2


def test_encode_stage_worker_output_closes_writer_when_frame_count_mismatches(tmp_path: Path) -> None:
    chunk = StageChunkPlan(
        input_start_frame=0,
        input_frame_count=2,
        logical_input_frame_count=2,
        raw_output_frame_count=2,
        written_output_frame_count=2,
        skip_output_frames=0,
    )
    stdout = BytesIO(np.ascontiguousarray(_frame(1)).tobytes())
    ffmpeg = FakeRawVideoMedia(payload=b"encoded")

    with pytest.raises(RuntimeError, match="Stage chunk output frame count mismatch"):
        encode_stage_worker_output(
            config=_runtime_config(ffmpeg, PipelineMetrics()),
            output_path=str(tmp_path / "chunk.mp4"),
            worker_stdout=stdout,
            chunk=chunk,
        )

    assert ffmpeg.writer is not None
    assert ffmpeg.writer.closed is True
