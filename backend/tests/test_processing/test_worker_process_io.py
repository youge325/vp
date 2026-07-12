from __future__ import annotations

import io
import queue
import threading
from types import SimpleNamespace

import numpy as np

from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.processing.streaming.worker_process_io import (
    DecodedFrameWriterConfig,
    drain_final_worker_output,
    start_decoded_frame_writer,
)


class _FakeReader:
    def __init__(self, frames: list[np.ndarray]) -> None:
        self.frames = list(frames)
        self.closed = False

    def read_frame(self) -> np.ndarray | None:
        if not self.frames:
            return None
        return self.frames.pop(0)

    def close(self) -> None:
        self.closed = True


class _FakeFFmpeg:
    def __init__(self, reader: _FakeReader) -> None:
        self.reader = reader
        self.decoder_args: dict | None = None

    def open_rawvideo_decoder(self, **kwargs):
        self.decoder_args = kwargs
        return self.reader


class _FakeStdin(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.was_closed = False

    def close(self) -> None:
        self.was_closed = True


def test_start_decoded_frame_writer_streams_frames_and_closes_reader() -> None:
    frames = [np.array([[[1, 2, 3]]], dtype=np.uint8), np.array([[[4, 5, 6]]], dtype=np.uint8)]
    reader = _FakeReader(frames)
    ffmpeg = _FakeFFmpeg(reader)
    stdin = _FakeStdin()
    error_queue: queue.Queue[BaseException] = queue.Queue()

    thread = start_decoded_frame_writer(
        DecodedFrameWriterConfig(
            ffmpeg=ffmpeg,
            input_path="input.mp4",
            decode_config={"mode": "software"},
            video_info={"width": 1, "height": 1},
            start_source_frame=3,
            worker_stdin=stdin,
            error_queue=error_queue,
            stop_event=threading.Event(),
            frame_count=2,
        ),
        thread_name="vp-test-decoder",
    )
    thread.join()

    assert error_queue.empty()
    assert reader.closed is True
    assert stdin.was_closed is True
    assert stdin.getvalue() == b"\x01\x02\x03\x04\x05\x06"
    assert ffmpeg.decoder_args == {
        "input_path": "input.mp4",
        "width": 1,
        "height": 1,
        "decode_config": {"mode": "software"},
        "start_frame": 3,
        "frame_count": 2,
    }
    assert thread.name == "vp-test-decoder"
    assert thread.daemon is True


def test_drain_final_worker_output_stops_after_expected_frame_count() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan([step], 1, source_duration=1.0, output_fps=None)
    final_plan = StageWorkerPlan(
        config=StageWorkerConfig(
            stage=step,
            stage_index=1,
            stage_total=1,
            stage_name="01_super_resolution",
            input_width=1,
            input_height=1,
            output_width=1,
            output_height=1,
            input_frame_count=1,
            tensor_backend_name="onnx",
        ),
        output_frame_count=1,
    )
    final_stdout = io.BytesIO(np.array([[[1, 2, 3]]], dtype=np.uint8).tobytes() + b"tail")
    encode_queue: queue.Queue = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    drain_final_worker_output(
        final_stdout=final_stdout,
        final_plan=final_plan,
        stage_plan=stage_plan,
        resume_state=SimpleNamespace(completed_output_frames=0, start_source_frame=0),
        source_frames=1,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=PipelineMetrics(),
    )

    assert error_queue.empty()
    item = encode_queue.get_nowait()
    assert isinstance(item, EncodedFrame)
    assert int(item.frame[0, 0, 0]) == 1
