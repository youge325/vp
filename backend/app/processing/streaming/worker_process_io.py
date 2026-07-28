"""Parent-side rawvideo I/O helpers for stage-worker subprocesses."""

from __future__ import annotations

from contextlib import contextmanager
import queue
import threading
from dataclasses import dataclass
from typing import Any, BinaryIO, Iterator

from app.planning import StagePlan
from app.planning.manifest import ResumeState
from app.ports.media import RawVideoPort
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodeQueue, EncodedFrame, SegmentBoundary, _queue_put
from app.processing.streaming.stage_worker_io import read_rgb_frame, write_rgb_frame
from app.processing.streaming.worker_plans import StageWorkerPlan, boundary_schedule_for_stage_plan


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


def _write_decoded_frames_to_worker(config: DecodedFrameWriterConfig) -> None:
    if config.worker_stdin is None:
        config.error_queue.put(RuntimeError("Stage worker stdin is unavailable."))
        config.stop_event.set()
        return
    reader = None
    try:
        reader = config.ffmpeg.open_rawvideo_decoder(
            input_path=config.input_path,
            width=config.width,
            height=config.height,
            decode_config=config.decode_config,
            start_frame=config.start_source_frame,
            frame_count=config.frame_count,
        )
        while not config.stop_event.is_set():
            frame = reader.read_frame()
            if frame is None:
                break
            write_rgb_frame(
                config.worker_stdin,
                frame,
                width=config.width,
                height=config.height,
            )
        config.worker_stdin.close()
    except BaseException as exc:  # pragma: no cover - thread boundary
        config.stop_event.set()
        config.error_queue.put(exc)
        close_pipe(config.worker_stdin)
    finally:
        if reader is not None:
            try:
                reader.close()
            except BaseException as exc:  # pragma: no cover - close failures are real pipeline failures
                config.stop_event.set()
                config.error_queue.put(exc)


@contextmanager
def decoded_frame_writer_session(
    config: DecodedFrameWriterConfig,
    *,
    thread_name: str,
) -> Iterator[None]:
    thread = threading.Thread(
        target=_write_decoded_frames_to_worker,
        name=thread_name,
        args=(config,),
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        thread.join()


def drain_final_worker_output(
    *,
    final_stdout: BinaryIO | None,
    final_plan: StageWorkerPlan,
    stage_plan: StagePlan,
    resume_state: ResumeState,
    source_frames: int,
    encode_queue: EncodeQueue,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
) -> None:
    if final_stdout is None:
        stop_event.set()
        error_queue.put(RuntimeError("Final stage worker stdout is unavailable."))
        return

    emitted_count = 0
    boundary_schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=int(resume_state.start_source_frame),
        source_frames=source_frames,
    )
    try:
        while not stop_event.is_set() and emitted_count < final_plan.output_frame_count:
            frame = read_rgb_frame(
                final_stdout,
                width=final_plan.config.output_width,
                height=final_plan.config.output_height,
            )
            if frame is None:
                break
            emitted_count += 1
            _queue_put(encode_queue, EncodedFrame(frame=frame), stop_event)
            metrics.set_queue_depth("encode", encode_queue.qsize())
            next_source_frame = boundary_schedule.get(emitted_count)
            if next_source_frame is not None:
                _queue_put(encode_queue, SegmentBoundary(next_source_frame=next_source_frame), stop_event)
        if emitted_count != final_plan.output_frame_count and not stop_event.is_set():
            raise RuntimeError(
                "Stage worker output frame count mismatch: "
                f"expected {final_plan.output_frame_count}, got {emitted_count}."
            )
    except BaseException as exc:
        stop_event.set()
        error_queue.put(exc)


def close_pipe(pipe: BinaryIO | None) -> None:
    if pipe is None:
        return
    try:
        pipe.close()
    except Exception:
        pass


__all__ = [
    "DecodedFrameWriterConfig",
    "close_pipe",
    "decoded_frame_writer_session",
    "drain_final_worker_output",
]
