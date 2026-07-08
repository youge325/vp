"""Parent-side rawvideo worker pipeline helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
from typing import Any

from app.planning import ProcessingStep, StagePlan
from app.planning.manifest import ResumeState, SegmentManifest
from app.processing.streaming.encoder import _finalize_segmented_output, _resolve_segment_output_frame_count
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    StreamEnd,
    _ENCODE_END,
    _queue_put,
    _queue_put_nowait,
)
from app.processing.streaming.stage_worker import StageWorkerConfig, read_rgb_frame
from app.processing.streaming.stage_rules import (
    ordered_steps,
    stage_output_dimensions,
    stage_output_fps,
    stage_output_frame_count,
    stage_progress_total,
    stage_tensor_backend_name,
)
from app.processing.streaming.worker_plans import (
    StageChunkPlan,
    StageWorkerPlan,
    boundary_schedule_for_stage_plan,
    build_stage_chunk_plans,
    build_stage_worker_plans,
)
from app.processing.streaming.worker_processes import (
    close_pipe,
    drain_final_worker_output,
    parse_stage_event_line,
    read_worker_stderr,
    spawn_stage_workers,
    wait_for_workers,
    write_decoded_frames_to_worker,
)


def run_stage_worker_pipeline(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Any],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
    python_executable: str | None = None,
) -> None:
    """Run algorithm stages as isolated rawvideo subprocesses.

    The function pushes ``EncodedFrame`` / ``SegmentBoundary`` / ``StreamEnd``
    packets into ``encode_queue`` for the existing encoder worker.
    """
    start_source_frame = int(resume_state.start_source_frame)
    remaining_source_frames = max(int(video_info["source_frames"]) - start_source_frame, 0)
    if remaining_source_frames <= 0:
        _queue_put(encode_queue, StreamEnd(next_source_frame=int(video_info["source_frames"])), stop_event)
        return

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
        source_width=int(video_info["width"]),
        source_height=int(video_info["height"]),
        source_frame_count=remaining_source_frames,
    )
    if not plans:
        raise RuntimeError("Worker pipeline requires at least one processing stage.")

    with tempfile.TemporaryDirectory(prefix="vp-stage-workers-") as config_dir:
        handles = spawn_stage_workers(
            plans,
            config_dir=Path(config_dir),
            python_executable=python_executable or sys.executable,
        )
        stderr_threads = [
            threading.Thread(
                target=read_worker_stderr,
                name=f"vp-stage-worker-stderr-{handle.plan.config.stage_index}",
                args=(handle, progress_callbacks, error_queue, stop_event),
                daemon=True,
            )
            for handle in handles
        ]
        for thread in stderr_threads:
            thread.start()

        decode_thread = threading.Thread(
            target=write_decoded_frames_to_worker,
            name="vp-stage-worker-decode-writer",
            kwargs={
                "ffmpeg": ffmpeg,
                "input_path": input_path,
                "decode_config": decode_config,
                "video_info": video_info,
                "start_source_frame": start_source_frame,
                "worker_stdin": handles[0].process.stdin,
                "error_queue": error_queue,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        decode_thread.start()

        try:
            drain_final_worker_output(
                final_stdout=handles[-1].process.stdout,
                final_plan=plans[-1],
                stage_plan=stage_plan,
                resume_state=resume_state,
                source_frames=int(video_info["source_frames"]),
                encode_queue=encode_queue,
                error_queue=error_queue,
                stop_event=stop_event,
                metrics=metrics,
            )
        finally:
            decode_thread.join()
            for handle in handles:
                close_pipe(handle.process.stdin)
                close_pipe(handle.process.stdout)
            wait_for_workers(handles, error_queue)
            for thread in stderr_threads:
                thread.join(timeout=1)

    if not error_queue.empty():
        _queue_put_nowait(encode_queue, _ENCODE_END)
        return
    _queue_put(encode_queue, StreamEnd(next_source_frame=int(video_info["source_frames"])), stop_event)


def run_stage_file_pipeline(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Any],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    segment_frames: int,
    output_path: str,
    output_fps: float | None,
    metrics: PipelineMetrics,
    python_executable: str | None = None,
) -> int:
    """Run each algorithm stage as segmented files instead of one rawvideo chain."""
    steps = ordered_steps(stage_plan)
    if not steps:
        raise RuntimeError("Stage file pipeline requires at least one processing stage.")

    stage_root = manifest.sidecar_dir / "stages"
    stage_root.mkdir(parents=True, exist_ok=True)

    current_path = input_path
    current_width = int(video_info["width"])
    current_height = int(video_info["height"])
    current_fps = float(video_info["source_fps"])
    current_frame_count = int(video_info["source_frames"])
    completed_frames = int(resume_state.completed_output_frames)

    for stage_position, step in enumerate(steps, start=1):
        is_final_stage = stage_position == len(steps)
        output_width, output_height = stage_output_dimensions(
            step,
            input_width=current_width,
            input_height=current_height,
        )
        stage_output_frames = stage_output_frame_count(step, current_frame_count)
        stage_fps = stage_output_fps(step, current_fps)

        if is_final_stage:
            stage_manifest = manifest
            stage_output_path = output_path
            stage_resume_state = resume_state
            stage_start_frame = min(int(resume_state.start_source_frame), current_frame_count)
            stage_chunk_start_index = len(resume_state.completed_segments) + 1
            stage_encode_output_fps = output_fps
            stage_encode_config = encode_config
        else:
            stage_output_path = str(stage_root / f"stage-{stage_position:02d}-{_safe_stage_name(step)}.mp4")
            stage_manifest = SegmentManifest(stage_output_path)
            stage_manifest.prepare(
                _stage_signature(stage_position, step, current_path, stage_output_path),
                {
                    "input_path": current_path,
                    "output_path": stage_output_path,
                    "stage": step.to_jsonable(),
                    "segmentFrames": max(1, int(segment_frames)),
                },
                mode="force-fresh",
            )
            stage_resume_state = _empty_resume_state()
            stage_start_frame = 0
            stage_chunk_start_index = 1
            stage_encode_output_fps = None
            stage_encode_config = {**encode_config, "keepAudio": False}

        completed_frames = _run_single_stage_file_chunks(
            ffmpeg=ffmpeg,
            input_path=current_path,
            decode_config=decode_config,
            encode_config=stage_encode_config,
            manifest=stage_manifest,
            step=step,
            stage_index=stage_position,
            stage_total=len(steps),
            tensor_backend_name=stage_tensor_backend_name(step, tensor_backend_name),
            progress_callback=progress_callbacks[stage_position - 1]
            if stage_position - 1 < len(progress_callbacks)
            else None,
            input_width=current_width,
            input_height=current_height,
            output_width=output_width,
            output_height=output_height,
            input_frame_count=current_frame_count,
            output_frame_count=stage_output_frames,
            input_fps=current_fps,
            output_fps=stage_fps,
            encode_output_fps=stage_encode_output_fps,
            resume_state=stage_resume_state,
            start_frame=stage_start_frame,
            start_chunk_index=stage_chunk_start_index,
            segment_frames=segment_frames,
            metrics=metrics,
            python_executable=python_executable or sys.executable,
        )

        if is_final_stage:
            return completed_frames

        finalized = _finalize_segmented_output(
            ffmpeg=ffmpeg,
            input_path=current_path,
            output_path=stage_output_path,
            encode_config=stage_encode_config,
            manifest=stage_manifest,
            signature="",
            completed_output_frames=completed_frames,
            total_output_frames=stage_output_frames,
            strict_total_frames=True,
        )
        stage_manifest.cleanup()
        current_path = finalized
        current_width = output_width
        current_height = output_height
        current_fps = stage_fps
        current_frame_count = stage_output_frames

    return completed_frames


def _run_single_stage_file_chunks(
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
        actual_written = _run_stage_chunk_to_file(
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


def _run_stage_chunk_to_file(
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
            callbacks[stage_index - 1] = _chunk_progress_adapter(
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


def _chunk_progress_adapter(
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
            current_value = min(_stage_chunk_output_start(step, chunk) + max(int(current), 0), total)
        callback(current_value, total, **kwargs)

    return adapter


def _stage_chunk_output_start(step: ProcessingStep, chunk: StageChunkPlan) -> int:
    if step.algorithm_type != "frame_interpolation":
        return chunk.input_start_frame
    multi = int(step.algorithm_kwargs.get("multi") or 2)
    if chunk.input_start_frame <= 0:
        return 0
    return chunk.input_start_frame + chunk.input_start_frame * (multi - 1)


def _empty_resume_state() -> ResumeState:
    return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])


def _stage_signature(stage_position: int, step: ProcessingStep, input_path: str, output_path: str) -> str:
    return json.dumps(
        {
            "stage": stage_position,
            "step": step.to_jsonable(),
            "input": os.path.abspath(input_path),
            "output": os.path.abspath(output_path),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _safe_stage_name(step: ProcessingStep) -> str:
    name = step.stage_name or step.algorithm_type or "stage"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)


__all__ = [
    "StageChunkPlan",
    "StageWorkerPlan",
    "boundary_schedule_for_stage_plan",
    "build_stage_chunk_plans",
    "build_stage_worker_plans",
    "parse_stage_event_line",
    "run_stage_file_pipeline",
    "run_stage_worker_pipeline",
]
