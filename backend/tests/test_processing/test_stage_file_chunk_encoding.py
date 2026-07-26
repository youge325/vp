from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.planning import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_chunk_encoding import encode_stage_worker_output
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from app.processing.streaming.worker_plans import StageChunkPlan


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


class _FakeWriter:
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self.frames: list[np.ndarray] = []
        self.output_frame_count = 0
        self.closed = False

    def write_frame(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def close(self) -> None:
        self.closed = True
        self.output_frame_count = len(self.frames)
        Path(self.output_path).write_bytes(b"encoded")


class _FakeFFmpeg:
    def __init__(self) -> None:
        self.writer: _FakeWriter | None = None

    def open_rawvideo_encoder(self, *, output_path: str, **kwargs: Any) -> _FakeWriter:
        del kwargs
        self.writer = _FakeWriter(output_path)
        return self.writer

    def get_frame_count(self, _path: str) -> int:
        return 0


def _runtime_config(ffmpeg: Any, metrics: PipelineMetrics) -> StageFileRuntimeConfig:
    return StageFileRuntimeConfig(
        ffmpeg=ffmpeg,
        input_path="input.mp4",
        decode_config={},
        encode_config={"container": "mp4"},
        step=ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 1.0},
            stage_name="01_super_resolution",
        ),
        stage_index=1,
        stage_total=1,
        tensor_backend_name="paddle",
        progress_callback=None,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        output_fps=24.0,
        encode_output_fps=None,
        metrics=metrics,
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
    ffmpeg = _FakeFFmpeg()
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
    ffmpeg = _FakeFFmpeg()

    with pytest.raises(RuntimeError, match="Stage chunk output frame count mismatch"):
        encode_stage_worker_output(
            config=_runtime_config(ffmpeg, PipelineMetrics()),
            output_path=str(tmp_path / "chunk.mp4"),
            worker_stdout=stdout,
            chunk=chunk,
        )

    assert ffmpeg.writer is not None
    assert ffmpeg.writer.closed is True
