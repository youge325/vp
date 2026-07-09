"""Single chunk runtime for file-backed stage execution."""

from __future__ import annotations

from pathlib import Path
import queue
import tempfile
import threading
from typing import Any

from app.planning import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_chunk_encoding import encode_stage_worker_output
from app.processing.streaming.stage_file_chunk_progress import chunk_progress_adapter
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.worker_plans import StageChunkPlan, StageWorkerPlan
from app.processing.streaming.worker_process_events import read_worker_stderr
from app.processing.streaming.worker_process_io import close_pipe, write_decoded_frames_to_worker
from app.processing.streaming.worker_processes import (
    spawn_stage_workers,
    wait_for_workers,
)


def run_stage_chunk_to_file(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    output_path: str,
    step: ProcessingStep,
    stage_index: int,
    stage_total: int,
    tensor_backend_name: str,
    progress_callback: Any,
    chunk: StageChunkPlan,
    input_width: int,
    input_height: int,
    output_width: int,
    output_height: int,
    stage_total_frames: int,
    output_fps: float,
    encode_output_fps: float | None,
    metrics: PipelineMetrics,
    python_executable: str,
) -> int:
    config = StageWorkerConfig(
        stage=step,
        stage_index=stage_index,
        stage_total=stage_total,
        stage_name=step.stage_name or step.algorithm_type,
        input_width=input_width,
        input_height=input_height,
        output_width=output_width,
        output_height=output_height,
        input_frame_count=chunk.input_frame_count,
        tensor_backend_name=tensor_backend_name,
        output_frame_count=chunk.raw_output_frame_count,
    )
    plan = StageWorkerPlan(config=config, output_frame_count=chunk.raw_output_frame_count)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    with tempfile.TemporaryDirectory(prefix="vp-stage-chunk-") as config_dir:
        handle = spawn_stage_workers([plan], config_dir=Path(config_dir), python_executable=python_executable)[0]
        callbacks: list[Any | None] = []
        if progress_callback is not None:
            callbacks = [None] * stage_total
            callbacks[stage_index - 1] = chunk_progress_adapter(
                step,
                chunk=chunk,
                total=stage_total_frames,
                callback=progress_callback,
            )
        stderr_thread = threading.Thread(
            target=read_worker_stderr,
            name=f"vp-stage-file-stderr-{stage_index}",
            args=(handle, callbacks, error_queue, stop_event),
            daemon=True,
        )
        stderr_thread.start()

        decode_thread = threading.Thread(
            target=write_decoded_frames_to_worker,
            name=f"vp-stage-file-decode-{stage_index}",
            kwargs={
                "ffmpeg": ffmpeg,
                "input_path": input_path,
                "decode_config": decode_config,
                "video_info": {
                    "width": input_width,
                    "height": input_height,
                },
                "start_source_frame": chunk.input_start_frame,
                "frame_count": chunk.input_frame_count,
                "worker_stdin": handle.process.stdin,
                "error_queue": error_queue,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        decode_thread.start()

        try:
            if handle.process.stdout is None:
                raise RuntimeError("Stage worker stdout is unavailable.")
            encoded_frames = encode_stage_worker_output(
                ffmpeg=ffmpeg,
                encode_config=encode_config,
                output_path=output_path,
                worker_stdout=handle.process.stdout,
                chunk=chunk,
                output_width=output_width,
                output_height=output_height,
                output_fps=output_fps,
                encode_output_fps=encode_output_fps,
                metrics=metrics,
            )
            if not error_queue.empty():
                raise error_queue.get()
            return encoded_frames
        except BaseException as exc:
            stop_event.set()
            error_queue.put(exc)
            raise
        finally:
            decode_thread.join()
            close_pipe(handle.process.stdin)
            close_pipe(handle.process.stdout)
            wait_for_workers([handle], error_queue)
            stderr_thread.join(timeout=1)
            if not error_queue.empty():
                raise error_queue.get()


__all__ = ["run_stage_chunk_to_file"]
