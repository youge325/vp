"""Parent-side rawvideo I/O helpers for stage-worker subprocesses."""

from __future__ import annotations

import math
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, BinaryIO

from app.planning.stage_plan import StagePlan
from app.planning.manifest import ResumeState
from app.ports.media import RawVideoPort, RawVideoReaderPort
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.error_channel import report_first_error
from app.processing.streaming.queues import EncodeQueue, EncodedFrame, SegmentBoundary, _queue_put
from app.processing.streaming.stage_worker_io import read_rgb_frame, write_rgb_frame
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.worker_plans import boundary_schedule_for_stage_plan


@dataclass(frozen=True, slots=True)
class DecodedFrameWriterConfig:
    ffmpeg: RawVideoPort
    input_path: str
    decode_config: dict[str, Any]
    width: int
    height: int
    start_source_frame: int
    worker_stdin: BinaryIO | None
    error_queue: queue.Queue[BaseException]
    stop_event: threading.Event
    frame_count: int | None = None


class DecodedFrameWriter:
    """Owned decoder-to-worker pump with cooperative, bounded shutdown."""

    def __init__(self, config: DecodedFrameWriterConfig, *, thread_name: str) -> None:
        self._config = config
        self._stop_requested = threading.Event()
        self._reader_condition = threading.Condition()
        self._reader: RawVideoReaderPort | None = None
        self._reader_resolved = False
        self._reader_cleanup_in_progress = False
        self._reader_cleanup_complete = False
        self._reader_cleanup_error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name=thread_name, daemon=False)

    def start(self) -> None:
        self._thread.start()

    def signal_stop(self) -> None:
        self._stop_requested.set()

    def request_stop(self, *, deadline: float) -> bool:
        """Stop the decoder process without synchronously closing a busy pipe."""
        self.signal_stop()
        with self._reader_condition:
            while not self._reader_resolved or self._reader_cleanup_in_progress:
                remaining = max(deadline - time.monotonic(), 0.0)
                if remaining <= 0:
                    return False
                self._reader_condition.wait(timeout=remaining)
            if self._reader_cleanup_complete:
                return True
            reader = self._reader
            if reader is None:
                return False
            self._reader = None
            self._reader_cleanup_in_progress = True
        try:
            reaped = reader.terminate_and_reap(deadline=deadline)
        except BaseException as exc:  # pragma: no cover - adapter boundary
            self._finish_reader_cleanup(reader, succeeded=False, error=exc)
            return False
        self._finish_reader_cleanup(reader, succeeded=reaped)
        return reaped

    def join_until(self, *, deadline: float) -> bool:
        timeout = None if math.isinf(deadline) else max(deadline - time.monotonic(), 0.0)
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    @property
    def thread_name(self) -> str:
        return self._thread.name

    @property
    def cleanup_error(self) -> BaseException | None:
        with self._reader_condition:
            return self._reader_cleanup_error

    def _run(self) -> None:
        config = self._config
        if config.worker_stdin is None:
            self._resolve_without_reader()
            self._report_error(RuntimeError("Stage worker stdin is unavailable."))
            return
        reader: RawVideoReaderPort | None = None
        try:
            reader = config.ffmpeg.open_rawvideo_decoder(
                input_path=config.input_path,
                width=config.width,
                height=config.height,
                decode_config=config.decode_config,
                start_frame=config.start_source_frame,
                frame_count=config.frame_count,
            )
            with self._reader_condition:
                self._reader = reader
                self._reader_resolved = True
                self._reader_cleanup_complete = False
                self._reader_condition.notify_all()
            if self._stop_requested.is_set():
                return
            while not config.stop_event.is_set() and not self._stop_requested.is_set():
                frame = reader.read_frame()
                if frame is None:
                    break
                write_rgb_frame(
                    config.worker_stdin,
                    frame,
                    width=config.width,
                    height=config.height,
                )
            close_pipe(config.worker_stdin)
        except BaseException as exc:  # pragma: no cover - thread boundary
            if not self._stop_requested.is_set():
                self._report_error(exc)
            close_pipe(config.worker_stdin)
        finally:
            if reader is not None:
                if self._claim_reader(reader):
                    try:
                        reader.close()
                    except BaseException as exc:  # pragma: no cover - close failures are pipeline failures
                        self._finish_reader_cleanup(reader, succeeded=False, error=exc)
                        if not self._stop_requested.is_set():
                            self._report_error(exc)
                    else:
                        self._finish_reader_cleanup(reader, succeeded=True)
            else:
                self._resolve_without_reader()

    def _claim_reader(self, reader: RawVideoReaderPort) -> bool:
        with self._reader_condition:
            if self._reader is not reader or self._reader_cleanup_in_progress:
                return False
            self._reader = None
            self._reader_cleanup_in_progress = True
            return True

    def _finish_reader_cleanup(
        self,
        reader: RawVideoReaderPort,
        *,
        succeeded: bool,
        error: BaseException | None = None,
    ) -> None:
        with self._reader_condition:
            self._reader_cleanup_in_progress = False
            self._reader_cleanup_complete = succeeded
            if succeeded:
                self._reader = None
            else:
                self._reader = reader
            if error is not None and self._reader_cleanup_error is None:
                self._reader_cleanup_error = error
            self._reader_condition.notify_all()

    def _resolve_without_reader(self) -> None:
        with self._reader_condition:
            if self._reader_resolved:
                return
            self._reader_resolved = True
            self._reader_cleanup_complete = True
            self._reader_condition.notify_all()

    def _report_error(self, exc: BaseException) -> None:
        report_first_error(self._config.error_queue, self._config.stop_event, exc)


def drain_final_worker_output(
    *,
    final_stdout: BinaryIO | None,
    final_config: StageWorkerConfig,
    stage_plan: StagePlan,
    resume_state: ResumeState,
    source_frames: int,
    encode_queue: EncodeQueue,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    if final_stdout is None:
        report_first_error(error_queue, stop_event, RuntimeError("Final stage worker stdout is unavailable."))
        return

    expected_output_frames = int(final_config.output_frame_count)
    emitted_count = 0
    boundary_schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=int(resume_state.start_source_frame),
        source_frames=source_frames,
    )
    try:
        while not stop_event.is_set() and emitted_count < expected_output_frames:
            frame = read_rgb_frame(
                final_stdout,
                width=final_config.output_width,
                height=final_config.output_height,
            )
            if frame is None:
                break
            emitted_count += 1
            _queue_put(encode_queue, EncodedFrame(frame=frame), stop_event)
            metrics.set_queue_depth("encode", encode_queue.qsize())
            next_source_frame = boundary_schedule.get(emitted_count)
            if next_source_frame is not None:
                _queue_put(encode_queue, SegmentBoundary(next_source_frame=next_source_frame), stop_event)
        if emitted_count != expected_output_frames and not stop_event.is_set():
            raise RuntimeError(
                f"Stage worker output frame count mismatch: expected {expected_output_frames}, got {emitted_count}."
            )
    except BaseException as exc:
        report_first_error(error_queue, stop_event, exc)


def close_pipe(pipe: BinaryIO | None) -> None:
    if pipe is None:
        return
    try:
        pipe.close()
    except Exception:
        pass


__all__ = [
    "DecodedFrameWriterConfig",
    "DecodedFrameWriter",
    "close_pipe",
    "drain_final_worker_output",
]
