from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw import run_raw_streaming_pipeline
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd, _ENCODE_END


class _FakeWriter:
    def __init__(self, output_path: str, progress_callback: Any = None) -> None:
        self.output_path = output_path
        self.progress_callback = progress_callback
        self.frames: list[np.ndarray] = []
        self.output_frame_count = 0

    def write_frame(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def close(self) -> None:
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
        self.encoder_dimensions: list[tuple[int, int]] = []

    def open_rawvideo_encoder(
        self,
        *,
        output_path: str,
        width: int,
        height: int,
        progress_callback: Any = None,
        **kwargs: Any,
    ) -> _FakeWriter:
        del kwargs
        self.encoder_dimensions.append((width, height))
        return _FakeWriter(output_path, progress_callback=progress_callback)

    def get_frame_count(self, _path: str) -> int:
        return 0


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def test_raw_pipeline_runs_stage_worker_chain_into_segmented_encoder(tmp_path: Path, monkeypatch) -> None:
    ffmpeg = _FakeFFmpeg()
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    progress_events: list[tuple[int, str]] = []

    def fake_stage_worker_runner(**kwargs: Any) -> None:
        encode_queue = kwargs["encode_queue"]
        encode_queue.put(EncodedFrame(frame=_frame(10)))
        encode_queue.put(SegmentBoundary(next_source_frame=1))
        encode_queue.put(EncodedFrame(frame=_frame(20)))
        encode_queue.put(StreamEnd(next_source_frame=2))

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_raw.run_stage_worker_pipeline",
        fake_stage_worker_runner,
    )

    completed = run_raw_streaming_pipeline(
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        input_path=str(tmp_path / "in.mp4"),
        decode_config={"mode": "software"},
        encode_config={"container": "mp4"},
        manifest=manifest,
        stage_plan=StagePlan(
            pre_steps=[],
            interpolation_step=None,
            post_steps=[],
            total_encoded_frames=2,
        ),
        tensor_backend_name="onnx",
        progress_callbacks=[],
        video_info={"source_fps": 24.0, "source_frames": 2, "width": 1, "height": 1},
        output_width=1,
        output_height=1,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        segment_frames=1,
        output_path=str(tmp_path / "out.mp4"),
        output_fps=None,
        encode_progress_callback=lambda frame, _fps, _speed, _time, progress: progress_events.append((frame, progress)),
        metrics=PipelineMetrics(),
    )

    assert completed == 2
    assert ffmpeg.encoder_dimensions == [(1, 1), (1, 1)]
    assert progress_events == [(1, "end"), (2, "end")]
    assert [segment.next_source_frame for segment in manifest.scan_completed_chunks()] == [1, 2]


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
            ffmpeg=_FakeFFmpeg(),  # type: ignore[arg-type]
            input_path=str(tmp_path / "in.mp4"),
            decode_config={"mode": "software"},
            encode_config={"container": "mp4"},
            manifest=manifest,
            stage_plan=StagePlan(
                pre_steps=[],
                interpolation_step=None,
                post_steps=[],
                total_encoded_frames=0,
            ),
            tensor_backend_name="onnx",
            progress_callbacks=[],
            video_info={"source_fps": 24.0, "source_frames": 0, "width": 1, "height": 1},
            output_width=1,
            output_height=1,
            resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
            segment_frames=1,
            output_path=str(tmp_path / "out.mp4"),
            output_fps=None,
            encode_progress_callback=None,
            metrics=PipelineMetrics(),
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
            ffmpeg=_FakeFFmpeg(),  # type: ignore[arg-type]
            input_path=str(tmp_path / "in.mp4"),
            decode_config={"mode": "software"},
            encode_config={"container": "mp4"},
            manifest=SegmentManifest(str(tmp_path / "out.mp4")),
            stage_plan=StagePlan(pre_steps=[], interpolation_step=None, post_steps=[], total_encoded_frames=1),
            tensor_backend_name="onnx",
            progress_callbacks=[],
            video_info={"source_fps": 24.0, "source_frames": 1, "width": 1, "height": 1},
            output_width=1,
            output_height=1,
            resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
            segment_frames=1,
            output_path=str(tmp_path / "out.mp4"),
            output_fps=None,
            encode_progress_callback=None,
            metrics=PipelineMetrics(),
        )

    assert runtime["stop_event"].is_set()
    assert runtime["encode_queue"].get_nowait() is _ENCODE_END
    assert runtime["config"].width == 1
    assert runtime["config"].height == 1
    assert runtime["config"].fps == 24.0
    assert encoder_thread.joined is True
