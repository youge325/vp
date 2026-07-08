"""Chunk execution helpers for file-backed segmented stage pipelines."""

from __future__ import annotations

import os
from pathlib import Path
import queue
import tempfile
import threading
from typing import Any

from app.planning import ProcessingStep
from app.planning.manifest import ResumeState, SegmentManifest
from app.processing.streaming.encoder import _resolve_segment_output_frame_count
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_rules import stage_progress_total
from app.processing.streaming.stage_worker import StageWorkerConfig, read_rgb_frame
from app.processing.streaming.worker_plans import StageChunkPlan, StageWorkerPlan, build_stage_chunk_plans
from app.processing.streaming.worker_processes import (
    close_pipe,
    read_worker_stderr,
    spawn_stage_workers,
    wait_for_workers,
    write_decoded_frames_to_worker,
)


def run_single_stage_file_chunks(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    step: ProcessingStep,
    stage_index: int,
    stage_total: int,
    tensor_backend_name: str,
    progress_callback: Any,
    input_width: int,
    input_height: int,
    output_width: int,
    output_height: int,
    input_frame_count: int,
    output_frame_count: int,
    input_fps: float,
    output_fps: float,
    encode_output_fps: float | None,
    resume_state: ResumeState,
    start_frame: int,
    start_chunk_index: int,
    segment_frames: int,
    metrics: PipelineMetrics,
    python_executable: str,
) -> int:
    del input_fps
    extension = os.path.splitext(str(manifest.output_path))[1] or f".{encode_config.get('container') or 'mp4'}"
    chunks = [
        chunk
        for chunk in build_stage_chunk_plans(step, input_frame_count=input_frame_count, segment_frames=segment_frames)
        if chunk.input_start_frame >= start_frame
    ]
    if not chunks:
        return int(resume_state.completed_output_frames)

    output_start = int(resume_state.completed_output_frames)
    chunk_index = int(start_chunk_index)
    completed_output_frames = output_start

    for chunk in chunks:
        if chunk.written_output_frame_count <= 0:
            continue
        tmp_path = manifest.chunk_tmp_path(extension, index=chunk_index)
        actual_written = run_stage_chunk_to_file(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            encode_config=encode_config,
            output_path=tmp_path,
            step=step,
            stage_index=stage_index,
            stage_total=stage_total,
            tensor_backend_name=tensor_backend_name,
            progress_callback=progress_callback,
            chunk=chunk,
            input_width=input_width,
            input_height=input_height,
            output_width=output_width,
            output_height=output_height,
            stage_total_frames=stage_progress_total(step, input_frame_count, output_frame_count),
            output_fps=output_fps,
            encode_output_fps=encode_output_fps,
            metrics=metrics,
            python_executable=python_executable,
        )
        if actual_written <= 0:
            Path(tmp_path).unlink(missing_ok=True)
            continue
        manifest.finalize_chunk(
            tmp_path,
            index=chunk_index,
            start_output_frame=completed_output_frames,
            end_output_frame=completed_output_frames + actual_written - 1,
            next_source_frame=chunk.input_start_frame + chunk.logical_input_frame_count,
        )
        completed_output_frames += actual_written
        chunk_index += 1

    return completed_output_frames


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
    writer = None

    with tempfile.TemporaryDirectory(prefix="vp-stage-chunk-") as config_dir:
        handle = spawn_stage_workers([plan], config_dir=Path(config_dir), python_executable=python_executable)[0]
        callbacks = [(lambda *_args, **_kwargs: None) for _ in range(stage_total)]
        if progress_callback is not None:
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
            writer = ffmpeg.open_rawvideo_encoder(
                output_path=output_path,
                width=output_width,
                height=output_height,
                fps=output_fps,
                output_fps=encode_output_fps,
                encode_config=encode_config,
            )
            active_writer = writer
            written_frames = 0
            for raw_index in range(chunk.raw_output_frame_count):
                frame = read_rgb_frame(handle.process.stdout, width=output_width, height=output_height)
                if frame is None:
                    break
                if raw_index < chunk.skip_output_frames:
                    continue
                writer.write_frame(frame)
                written_frames += 1
                metrics.record_processed_frames(1)
            active_writer.close()
            writer = None
            encoded_frames = _resolve_segment_output_frame_count(
                ffmpeg,
                active_writer,
                output_path,
                fallback_frame_count=written_frames,
            )
            if not error_queue.empty():
                raise error_queue.get()
            if written_frames != chunk.written_output_frame_count:
                raise RuntimeError(
                    "Stage chunk output frame count mismatch: "
                    f"expected {chunk.written_output_frame_count}, got {written_frames}."
                )
            return encoded_frames
        except BaseException as exc:
            stop_event.set()
            error_queue.put(exc)
            raise
        finally:
            decode_thread.join()
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
            close_pipe(handle.process.stdin)
            close_pipe(handle.process.stdout)
            wait_for_workers([handle], error_queue)
            stderr_thread.join(timeout=1)
            if not error_queue.empty():
                raise error_queue.get()


def chunk_progress_adapter(
    step: ProcessingStep,
    *,
    chunk: StageChunkPlan,
    total: int,
    callback: Any,
) -> Any:
    def adapter(current: int, progress_total: int, **kwargs: Any) -> None:
        del progress_total
        if step.algorithm_type == "frame_interpolation":
            current_value = min(chunk.input_start_frame + max(int(current), 0), total)
        else:
            current_value = min(stage_chunk_output_start(step, chunk) + max(int(current), 0), total)
        callback(current_value, total, **kwargs)

    return adapter


def stage_chunk_output_start(step: ProcessingStep, chunk: StageChunkPlan) -> int:
    if step.algorithm_type != "frame_interpolation":
        return chunk.input_start_frame
    multi = int(step.algorithm_kwargs.get("multi") or 2)
    if chunk.input_start_frame <= 0:
        return 0
    return chunk.input_start_frame + chunk.input_start_frame * (multi - 1)


__all__ = [
    "chunk_progress_adapter",
    "run_single_stage_file_chunks",
    "run_stage_chunk_to_file",
    "stage_chunk_output_start",
]
