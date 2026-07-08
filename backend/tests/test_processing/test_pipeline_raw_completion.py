from __future__ import annotations

import queue
from pathlib import Path

import pytest

from app.planning import SegmentManifest
from app.processing.streaming.pipeline_raw_completion import finish_raw_pipeline_runtime


class _Joinable:
    def __init__(self) -> None:
        self.joined = False

    def join(self) -> None:
        self.joined = True


def _finalize_segment(
    manifest: SegmentManifest,
    *,
    index: int,
    start_output_frame: int,
    end_output_frame: int,
    next_source_frame: int,
) -> None:
    tmp_path = manifest.chunk_tmp_path(".mp4", index=index)
    Path(tmp_path).write_bytes(b"segment")
    manifest.finalize_chunk(
        tmp_path,
        index=index,
        start_output_frame=start_output_frame,
        end_output_frame=end_output_frame,
        next_source_frame=next_source_frame,
    )


def test_finish_raw_pipeline_runtime_joins_and_counts_completed_segments(tmp_path: Path) -> None:
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    _finalize_segment(manifest, index=1, start_output_frame=0, end_output_frame=1, next_source_frame=1)
    _finalize_segment(manifest, index=2, start_output_frame=2, end_output_frame=4, next_source_frame=3)
    encoder_thread = _Joinable()

    completed = finish_raw_pipeline_runtime(
        encoder_thread=encoder_thread,  # type: ignore[arg-type]
        error_queue=queue.Queue(),
        manifest=manifest,
    )

    assert completed == 5
    assert encoder_thread.joined is True


def test_finish_raw_pipeline_runtime_raises_worker_error_after_join(tmp_path: Path) -> None:
    error_queue: queue.Queue[BaseException] = queue.Queue()
    error_queue.put(RuntimeError("worker failed"))
    encoder_thread = _Joinable()

    with pytest.raises(RuntimeError, match="worker failed"):
        finish_raw_pipeline_runtime(
            encoder_thread=encoder_thread,  # type: ignore[arg-type]
            error_queue=error_queue,
            manifest=SegmentManifest(str(tmp_path / "out.mp4")),
        )

    assert encoder_thread.joined is True
