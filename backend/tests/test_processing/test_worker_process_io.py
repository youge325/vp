from __future__ import annotations

import io
import queue
import threading
import time
from types import SimpleNamespace

import numpy as np

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame
from app.processing.streaming.worker_process_io import (
    DecodedFrameWriter,
    DecodedFrameWriterConfig,
    drain_final_worker_output,
)
from app.processing.streaming.stage_worker_config import build_stage_worker_step


class _FakeReader:
    def __init__(self, frames: list[np.ndarray]) -> None:
        self.frames = list(frames)
        self.closed = False
        self.thread_name: str | None = None
        self.thread_daemon: bool | None = None

    def read_frame(self) -> np.ndarray | None:
        self.thread_name = threading.current_thread().name
        self.thread_daemon = threading.current_thread().daemon
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


def test_decoded_frame_writer_streams_frames_and_supports_bounded_shutdown() -> None:
    frames = [np.array([[[1, 2, 3]]], dtype=np.uint8), np.array([[[4, 5, 6]]], dtype=np.uint8)]
    reader = _FakeReader(frames)
    ffmpeg = _FakeFFmpeg(reader)
    stdin = _FakeStdin()
    error_queue: queue.Queue[BaseException] = queue.Queue()

    writer = DecodedFrameWriter(
        DecodedFrameWriterConfig(
            ffmpeg=ffmpeg,
            input_path="input.mp4",
            decode_config={"mode": "software"},
            width=1,
            height=1,
            start_source_frame=3,
            worker_stdin=stdin,
            error_queue=error_queue,
            stop_event=threading.Event(),
            frame_count=2,
        ),
        thread_name="vp-test-decoder",
    )
    writer.start()

    assert writer.join_until(deadline=float("inf")) is True

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
    assert reader.thread_name == "vp-test-decoder"
    assert reader.thread_daemon is False


def test_decoded_frame_writer_stop_unblocks_reader_before_bounded_join() -> None:
    entered_read = threading.Event()
    close_requested = threading.Event()

    class BlockingReader:
        terminate_calls = 0

        def read_frame(self) -> None:
            entered_read.set()
            close_requested.wait(timeout=1)
            return None

        def close(self) -> None:
            close_requested.set()

        def terminate_and_reap(self, *, deadline: float) -> bool:
            assert deadline >= time.monotonic()
            self.terminate_calls += 1
            close_requested.set()
            return True

    reader = BlockingReader()
    ffmpeg = _FakeFFmpeg(reader)  # type: ignore[arg-type]
    error_queue: queue.Queue[BaseException] = queue.Queue()
    writer = DecodedFrameWriter(
        DecodedFrameWriterConfig(
            ffmpeg=ffmpeg,
            input_path="input.mp4",
            decode_config={},
            width=1,
            height=1,
            start_source_frame=0,
            worker_stdin=_FakeStdin(),
            error_queue=error_queue,
            stop_event=threading.Event(),
        ),
        thread_name="vp-test-blocked-decoder",
    )
    writer.start()
    assert entered_read.wait(timeout=1)

    assert writer.request_stop(deadline=time.monotonic() + 1) is True

    assert writer.join_until(deadline=time.monotonic() + 1) is True
    assert close_requested.is_set()
    assert reader.terminate_calls == 1
    assert error_queue.empty()


def test_decoded_frame_writer_retains_reader_when_close_fails_until_reaped() -> None:
    class CloseFailingReader:
        terminate_calls = 0

        def read_frame(self) -> None:
            return None

        def close(self) -> None:
            raise OSError("decoder close failed")

        def terminate_and_reap(self, *, deadline: float) -> bool:
            assert deadline >= time.monotonic()
            self.terminate_calls += 1
            return True

    reader = CloseFailingReader()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    writer = DecodedFrameWriter(
        DecodedFrameWriterConfig(
            ffmpeg=_FakeFFmpeg(reader),  # type: ignore[arg-type]
            input_path="input.mp4",
            decode_config={},
            width=1,
            height=1,
            start_source_frame=0,
            worker_stdin=_FakeStdin(),
            error_queue=error_queue,
            stop_event=threading.Event(),
        ),
        thread_name="vp-test-close-failing-decoder",
    )
    writer.start()
    assert writer.join_until(deadline=time.monotonic() + 1) is True
    assert "decoder close failed" in str(error_queue.get_nowait())

    assert writer.request_stop(deadline=time.monotonic() + 1) is True
    assert reader.terminate_calls == 1


def test_decoded_frame_writer_stop_waits_for_decoder_open_and_reaps_arriving_owner() -> None:
    open_started = threading.Event()
    release_open = threading.Event()

    class ArrivingReader:
        terminate_calls = 0

        def read_frame(self) -> None:
            return None

        def close(self) -> None:
            raise OSError("late decoder close failed")

        def terminate_and_reap(self, *, deadline: float) -> bool:
            assert deadline >= time.monotonic()
            self.terminate_calls += 1
            return True

    class BlockingOpenFFmpeg:
        def __init__(self, reader) -> None:
            self.reader = reader

        def open_rawvideo_decoder(self, **_kwargs):
            open_started.set()
            release_open.wait(timeout=1)
            return self.reader

    reader = ArrivingReader()
    writer = DecodedFrameWriter(
        DecodedFrameWriterConfig(
            ffmpeg=BlockingOpenFFmpeg(reader),
            input_path="input.mp4",
            decode_config={},
            width=1,
            height=1,
            start_source_frame=0,
            worker_stdin=_FakeStdin(),
            error_queue=queue.Queue(),
            stop_event=threading.Event(),
        ),
        thread_name="vp-test-opening-decoder",
    )
    writer.start()
    assert open_started.wait(timeout=1)
    stop_result: list[bool] = []
    stop_thread = threading.Thread(
        target=lambda: stop_result.append(writer.request_stop(deadline=time.monotonic() + 1))
    )
    stop_thread.start()
    time.sleep(0.01)
    assert stop_thread.is_alive()

    release_open.set()
    stop_thread.join(timeout=1)

    assert stop_result == [True]
    assert reader.terminate_calls == 1
    assert writer.join_until(deadline=time.monotonic() + 1)


def test_drain_final_worker_output_stops_after_expected_frame_count() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": 1.0,
            "sr_algorithm": "placeholder",
            "onnx_model": "sr.onnx",
            "engine": "cuda",
            "num_frames": 10,
        },
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan(StageProjection((step,)), 1, source_duration=1.0, output_fps=None)
    final_config = StageWorkerConfig(
        stage=build_stage_worker_step(step),
        stage_index=1,
        stage_total=1,
        stage_name="01_super_resolution",
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        input_frame_count=1,
        tensor_backend_name="onnx",
        output_frame_count=1,
    )
    final_stdout = io.BytesIO(np.array([[[1, 2, 3]]], dtype=np.uint8).tobytes() + b"tail")
    encode_queue: queue.Queue = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    drain_final_worker_output(
        final_stdout=final_stdout,
        final_config=final_config,
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
