from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.planning import ResumeState, SegmentManifest, StagePlan, StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_context import (
    StreamingPipelineContext,
    StreamingPipelinePreflight,
)
from app.processing.streaming.pipeline_raw import run_raw_streaming_pipeline
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd, _ENCODE_END
from tests.support.raw_video import FakeRawVideoMedia, frame as _frame


def _context(
    tmp_path: Path,
    *,
    ffmpeg: Any,
    total_frames: int,
    source_frames: int,
    manifest: SegmentManifest | None = None,
    encode_progress_callback: Any = None,
) -> StreamingPipelineContext:
    manifest = manifest or SegmentManifest(str(tmp_path / "out.mp4"))
    stage_plan = StagePlan(
        projection=StageProjection(()),
        source_frames=total_frames,
        source_duration=total_frames / 24,
        output_fps=None,
    )
    return StreamingPipelineContext(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "in.mp4"),
        output_path=str(manifest.workspace.output_path),
        decode_config={"mode": "software"},
        encode_config={"container": "mp4"},
        preflight=StreamingPipelinePreflight(
            video_info=VideoMetadata(
                source_fps=24.0,
                source_frames=source_frames,
                width=1,
                height=1,
                duration=source_frames / 24,
                has_audio=False,
            ),
            stage_plan=stage_plan,
            signature="sig",
            config_snapshot={},
            use_stage_file_pipeline=False,
            resume_source_frames=source_frames,
            output_width=1,
            output_height=1,
            segment_frames=1,
        ),
        manifest=manifest,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        progress_callbacks=[],
        output_fps=None,
        encode_progress_callback=encode_progress_callback,
        metrics=PipelineMetrics(),
    )


def test_raw_pipeline_runs_stage_worker_chain_into_segmented_encoder(tmp_path: Path, monkeypatch) -> None:
    ffmpeg = FakeRawVideoMedia()
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    progress_events: list[tuple[int, str]] = []
    worker_configs = []

    def fake_stage_worker_runner(**kwargs: Any) -> None:
        worker_configs.append(kwargs["config"])
        encode_queue = kwargs["encode_queue"]
        encode_queue.put(EncodedFrame(frame=_frame(10)))
        encode_queue.put(SegmentBoundary(next_source_frame=1))
        encode_queue.put(EncodedFrame(frame=_frame(20)))
        encode_queue.put(StreamEnd(next_source_frame=2))

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_raw.run_stage_worker_pipeline",
        fake_stage_worker_runner,
    )

    context = _context(
        tmp_path,
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        total_frames=2,
        source_frames=2,
        manifest=manifest,
        encode_progress_callback=lambda frame, _fps, _speed, _time, progress: progress_events.append((frame, progress)),
    )
    completed = run_raw_streaming_pipeline(context=context)

    assert completed == 2
    assert ffmpeg.encoder_dimensions == [(1, 1), (1, 1)]
    assert progress_events == [(1, "end"), (2, "end")]
    assert [segment.next_source_frame for segment in manifest.scan_completed_chunks()] == [1, 2]
    assert len(worker_configs) == 1
    assert worker_configs[0].ffmpeg is context.ffmpeg
    assert worker_configs[0].decode_config is context.decode_config
    assert worker_configs[0].stage_plan is context.preflight.stage_plan
    assert worker_configs[0].resume_state is context.resume_state
    assert worker_configs[0].metrics is context.metrics


def test_raw_pipeline_raises_worker_error_after_encoder_shutdown(tmp_path: Path, monkeypatch) -> None:
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))

    def fake_stage_worker_runner(**kwargs: Any) -> None:
        kwargs["error_queue"].put(RuntimeError("worker failed"))
        kwargs["encode_queue"].put(StreamEnd(next_source_frame=0))

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_raw.run_stage_worker_pipeline",
        fake_stage_worker_runner,
    )

    with pytest.raises(RuntimeError, match="worker failed"):
        run_raw_streaming_pipeline(
            context=_context(
                tmp_path,
                ffmpeg=FakeRawVideoMedia(),  # type: ignore[arg-type]
                total_frames=0,
                source_frames=0,
                manifest=manifest,
            )
        )


def test_raw_pipeline_stops_and_joins_encoder_when_stage_worker_raises(tmp_path: Path, monkeypatch) -> None:
    runtime: dict[str, Any] = {}

    class _JoinableThread:
        joined = False

        def join(self) -> None:
            self.joined = True

    encoder_thread = _JoinableThread()

    def fake_start_encoder(**kwargs: Any) -> _JoinableThread:
        runtime.update(kwargs)
        return encoder_thread

    def fail_stage_worker(**_kwargs: Any) -> None:
        raise RuntimeError("spawn failed")

    monkeypatch.setattr("app.processing.streaming.pipeline_raw.start_raw_encoder_thread", fake_start_encoder)
    monkeypatch.setattr("app.processing.streaming.pipeline_raw.run_stage_worker_pipeline", fail_stage_worker)

    with pytest.raises(RuntimeError, match="spawn failed"):
        run_raw_streaming_pipeline(
            context=_context(
                tmp_path,
                ffmpeg=FakeRawVideoMedia(),  # type: ignore[arg-type]
                total_frames=1,
                source_frames=1,
                manifest=SegmentManifest(str(tmp_path / "out.mp4")),
            )
        )

    assert runtime["stop_event"].is_set()
    assert runtime["encode_queue"].get_nowait() is _ENCODE_END
    assert runtime["config"].width == 1
    assert runtime["config"].height == 1
    assert runtime["config"].fps == 24.0
    assert encoder_thread.joined is True
