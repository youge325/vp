"""Streaming video processing with bounded queues and segmented output."""

from __future__ import annotations

import json
import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from app.algorithms.factory import AlgorithmFactory
from app.algorithms.tensor_backend import get_tensor_backend
from app.errors import ResumeConflictError
from app.planning import (
    build_signature,
    build_stage_plan,
    resolve_video_info,
    ResumeMode,
    ResumeState,
    SegmentManifest,
    StagePlan,
)
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DECODE_END = object()
_ENCODE_END = object()


@dataclass(slots=True)
class DecodedFrame:
    """Decoded source frame packet."""

    source_index: int
    frame: np.ndarray


@dataclass(slots=True)
class EncodedFrame:
    """Processed frame ready to feed the encoder."""

    output_index: int
    frame: np.ndarray


@dataclass(slots=True)
class SegmentBoundary:
    """Natural split point after a full source-frame group."""

    next_source_frame: int


@dataclass(slots=True)
class StreamEnd:
    """Signal end-of-stream to the encoder stage."""

    next_source_frame: int


def process_video_streaming(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    output_fps: float | None = None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None = None,
    resume_mode: ResumeMode = "auto",
) -> dict[str, Any]:
    """Process a video without writing temporary frames to disk."""
    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        processing_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=output_fps,
    )
    signature = build_signature(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        video_info=video_info,
    )
    config_snapshot = _build_config_snapshot(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=processing_steps,
        video_info=video_info,
    )

    manifest = SegmentManifest(output_path)
    decision = manifest.prepare(signature, config_snapshot, mode=resume_mode)
    if decision.kind == "conflict_final_exists":
        raise ResumeConflictError(
            output_path=str(manifest.output_path),
            completed_chunks=len(decision.state.completed_segments),
            completed_output_frames=decision.state.completed_output_frames,
            sidecar_signature_match=decision.sidecar_signature_match,
        )

    resume_state = decision.state
    output_width, output_height = _resolved_output_dimensions(
        video_info=video_info,
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
    )

    if resume_state.start_source_frame >= video_info["source_frames"]:
        completed_output_frames = resume_state.completed_output_frames
    else:
        completed_output_frames = _run_streaming_pipeline(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            encode_config=encode_config,
            manifest=manifest,
            signature=signature,
            stage_plan=stage_plan,
            tensor_backend_name=tensor_backend_name,
            progress_callbacks=progress_callbacks,
            video_info=video_info,
            output_width=output_width,
            output_height=output_height,
            resume_state=resume_state,
            segment_frames=max(1, int(output_config.get("segmentFrames") or 1000)),
            output_path=output_path,
            output_fps=output_fps,
            encode_progress_callback=encode_progress_callback,
        )

    final_output = _finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        encode_config=encode_config,
        manifest=manifest,
        signature=signature,
        completed_output_frames=completed_output_frames,
        total_output_frames=stage_plan.total_encoded_frames,
        strict_total_frames=output_fps is None,
    )

    manifest.cleanup()
    processed_frames = ffmpeg.get_frame_count(final_output)
    return {
        "output_path": final_output,
        "processed_frames": processed_frames or completed_output_frames,
        "audio_merged": bool(encode_config.get("keepAudio", True)),
    }


def _build_config_snapshot(
    *,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    video_info: dict[str, Any],
) -> dict[str, Any]:
    """Capture the parameters that determine signature + behaviour for a run."""
    return {
        "input_path": os.path.abspath(input_path),
        "output_path": os.path.abspath(output_path),
        "decode_config": decode_config,
        "encode_config": encode_config,
        "workflow_config": workflow_config,
        "output_config": {
            "segmentFrames": max(1, int(output_config.get("segmentFrames") or 1000)),
        },
        "processing_steps": processing_steps,
        "video_info": {
            "width": video_info["width"],
            "height": video_info["height"],
            "source_fps": video_info["source_fps"],
            "source_frames": video_info["source_frames"],
        },
    }


def _run_streaming_pipeline(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    video_info: dict[str, Any],
    output_width: int,
    output_height: int,
    resume_state: ResumeState,
    segment_frames: int,
    output_path: str,
    output_fps: float | None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> int:
    decode_queue: queue.Queue[DecodedFrame | object] = queue.Queue(maxsize=100)
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    thread_args = {
        "decode_queue": decode_queue,
        "encode_queue": encode_queue,
        "error_queue": error_queue,
        "stop_event": stop_event,
    }

    threads = [
        threading.Thread(
            target=_decoder_worker,
            name="vp-decoder",
            kwargs={
                **thread_args,
                "ffmpeg": ffmpeg,
                "input_path": input_path,
                "decode_config": decode_config,
                "width": video_info["width"],
                "height": video_info["height"],
                "start_source_frame": resume_state.start_source_frame,
                "source_frames": video_info["source_frames"],
            },
            daemon=True,
        ),
        threading.Thread(
            target=_processor_worker,
            name="vp-processor",
            kwargs={
                **thread_args,
                "stage_plan": stage_plan,
                "tensor_backend_name": tensor_backend_name,
                "progress_callbacks": progress_callbacks,
                "source_frames": video_info["source_frames"],
                "resume_output_frames": resume_state.completed_output_frames,
            },
            daemon=True,
        ),
        threading.Thread(
            target=_encoder_worker,
            name="vp-encoder",
            kwargs={
                **thread_args,
                "ffmpeg": ffmpeg,
                "encode_config": encode_config,
                "manifest": manifest,
                "signature": signature,
                "width": output_width,
                "height": output_height,
                "fps": _resolved_stream_fps(video_info["source_fps"], stage_plan),
                "output_fps": output_fps,
                "segment_frames": segment_frames,
                "resume_state": resume_state,
                "output_path": output_path,
                "encode_progress_callback": encode_progress_callback,
            },
            daemon=True,
        ),
    ]

    _emit_resume_status_event(
        resume_state=resume_state,
        total_output_frames=stage_plan.total_encoded_frames,
    )

    if encode_progress_callback is not None and resume_state.completed_output_frames > 0:
        encode_progress_callback(
            resume_state.completed_output_frames,
            None,
            None,
            None,
            "continue",
        )

    for worker in threads:
        worker.start()

    for worker in threads:
        worker.join()

    if not error_queue.empty():
        raise error_queue.get()

    del signature
    completed_segments = manifest.read_completed_segments()
    return sum(segment.frame_count for segment in completed_segments)


def _resolved_stream_fps(source_fps: float, stage_plan: StagePlan) -> float:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        return source_fps
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or 2)
    return source_fps * multi


def _emit_resume_status_event(*, resume_state: ResumeState, total_output_frames: int) -> None:
    """Emit a structured resume_status JSON line consumed by the Tauri host."""
    payload = {
        "type": "resume_status",
        "resumed": resume_state.completed_output_frames > 0,
        "completedChunks": len(resume_state.completed_segments),
        "completedOutputFrames": resume_state.completed_output_frames,
        "startSourceFrame": resume_state.start_source_frame,
        "totalOutputFrames": total_output_frames,
    }
    try:
        print(json.dumps(payload, ensure_ascii=False), flush=True)
    except Exception:  # pragma: no cover - never let telemetry break the pipeline
        logger.exception("Failed to emit resume_status event")


def _resolved_output_dimensions(
    *,
    video_info: dict[str, Any],
    stage_plan: StagePlan,
    tensor_backend_name: str,
) -> tuple[int, int]:
    width = int(video_info["width"])
    height = int(video_info["height"])
    if tensor_backend_name != "onnx":
        return width, height

    for step in [*stage_plan.pre_steps, *stage_plan.post_steps]:
        if step["algorithm_type"] != "super_resolution":
            continue
        kwargs = step["algorithm_kwargs"]
        if not kwargs.get("onnx_model"):
            continue
        scale_factor = float(kwargs.get("scale_factor") or 1.0)
        width = max(1, int(round(width * scale_factor)))
        height = max(1, int(round(height * scale_factor)))

    return width, height


def _decoder_worker(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    width: int,
    height: int,
    start_source_frame: int,
    source_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    del encode_queue
    try:
        if start_source_frame >= source_frames:
            _queue_put(decode_queue, _DECODE_END, stop_event)
            return

        reader = ffmpeg.open_rawvideo_decoder(
            input_path=input_path,
            width=width,
            height=height,
            decode_config=decode_config,
            start_frame=start_source_frame,
        )
        try:
            source_index = start_source_frame
            while not stop_event.is_set():
                frame = reader.read_frame()
                if frame is None:
                    break
                _queue_put(decode_queue, DecodedFrame(source_index=source_index, frame=frame), stop_event)
                source_index += 1
        finally:
            reader.close()

        _queue_put(decode_queue, _DECODE_END, stop_event)
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        _queue_put_nowait(decode_queue, _DECODE_END)


def _processor_worker(
    *,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> None:
    try:
        algorithms = _initialize_algorithms(stage_plan, tensor_backend_name)

        if stage_plan.interpolation_step is None:
            _process_single_frame_stream(
                stage_plan=stage_plan,
                algorithms=algorithms,
                progress_callbacks=progress_callbacks,
                source_frames=source_frames,
                resume_output_frames=resume_output_frames,
                decode_queue=decode_queue,
                encode_queue=encode_queue,
                stop_event=stop_event,
            )
        else:
            _process_interpolated_stream(
                stage_plan=stage_plan,
                algorithms=algorithms,
                progress_callbacks=progress_callbacks,
                source_frames=source_frames,
                resume_output_frames=resume_output_frames,
                decode_queue=decode_queue,
                encode_queue=encode_queue,
                stop_event=stop_event,
            )
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        _queue_put_nowait(encode_queue, _ENCODE_END)


def _encoder_worker(
    *,
    ffmpeg: FFmpegWrapper,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    width: int,
    height: int,
    fps: float,
    output_fps: float | None,
    segment_frames: int,
    resume_state: ResumeState,
    output_path: str,
    decode_queue: queue.Queue[Any],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> None:
    del decode_queue, signature
    extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
    writer = None
    segment_index = len(resume_state.completed_segments) + 1
    current_segment_start = resume_state.completed_output_frames
    current_segment_input_frames = 0
    tmp_path = ""

    def seal_chunk(next_source_frame: int) -> None:
        nonlocal writer, segment_index, current_segment_start, current_segment_input_frames, tmp_path
        assert writer is not None
        writer.close()
        try:
            segment_output_frames = _resolve_segment_output_frame_count(
                ffmpeg,
                writer,
                tmp_path,
                fallback_frame_count=current_segment_input_frames,
            )
        finally:
            writer = None
        if segment_output_frames <= 0:
            # Encoder produced no frames; drop the sentinel and reset.
            Path(tmp_path).unlink(missing_ok=True)
            current_segment_input_frames = 0
            tmp_path = ""
            return
        manifest.finalize_chunk(
            tmp_path,
            index=segment_index,
            start_output_frame=current_segment_start,
            end_output_frame=current_segment_start + segment_output_frames - 1,
            next_source_frame=next_source_frame,
        )
        segment_index += 1
        current_segment_start += segment_output_frames
        current_segment_input_frames = 0
        tmp_path = ""

    try:
        while not stop_event.is_set():
            item = _queue_get(encode_queue, stop_event)
            if item is None:
                continue

            if item is _ENCODE_END:
                break

            if isinstance(item, EncodedFrame):
                if writer is None:
                    tmp_path = manifest.chunk_tmp_path(extension, index=segment_index)
                    writer = ffmpeg.open_rawvideo_encoder(
                        output_path=tmp_path,
                        width=width,
                        height=height,
                        fps=fps,
                        output_fps=output_fps,
                        encode_config=encode_config,
                        progress_callback=_make_segment_progress_callback(
                            current_segment_start,
                            encode_progress_callback,
                        ),
                    )
                writer.write_frame(item.frame)
                current_segment_input_frames += 1
                continue

            if isinstance(item, SegmentBoundary):
                if writer is None:
                    continue
                if current_segment_input_frames < segment_frames:
                    continue
                seal_chunk(item.next_source_frame)
                continue

            if isinstance(item, StreamEnd):
                if writer is not None and current_segment_input_frames > 0:
                    seal_chunk(item.next_source_frame)
                break
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:  # pragma: no cover - cleanup best effort
                pass
        # Discard any in-flight sentinel left behind by an exception or cancel.
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - cleanup best effort
                pass


def _make_segment_progress_callback(
    segment_start_frame: int,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
) -> Callable[[dict[str, Any]], None] | None:
    if encode_progress_callback is None:
        return None

    def callback(progress: dict[str, Any]) -> None:
        encode_progress_callback(
            segment_start_frame + int(progress.get("frame") or 0),
            progress.get("fps"),
            progress.get("speed"),
            progress.get("out_time_seconds"),
            str(progress.get("progress") or ""),
        )

    return callback


def _resolve_segment_output_frame_count(
    ffmpeg: FFmpegWrapper,
    writer: Any,
    segment_path: str,
    *,
    fallback_frame_count: int,
) -> int:
    output_frame_count = int(getattr(writer, "output_frame_count", 0) or 0)
    if output_frame_count > 0:
        return output_frame_count
    return ffmpeg.get_frame_count(segment_path) or fallback_frame_count


def _initialize_algorithms(stage_plan: StagePlan, tensor_backend_name: str) -> dict[str, Any]:
    algorithms: dict[str, Any] = {
        "single": [],
        "post": [],
        "interpolation": None,
    }

    for step in stage_plan.pre_steps:
        backend = get_tensor_backend(tensor_backend_name)
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["single"].append((step, backend, algorithm))

    if stage_plan.interpolation_step is not None:
        backend = get_tensor_backend(tensor_backend_name)
        algorithm = AlgorithmFactory.create(
            algorithm_type=stage_plan.interpolation_step["algorithm_type"],
            tensor_backend=backend,
            tensor_backend_name=tensor_backend_name,
            **stage_plan.interpolation_step["algorithm_kwargs"],
        )
        algorithms["interpolation"] = (backend, algorithm)

    for step in stage_plan.post_steps:
        backend = get_tensor_backend(tensor_backend_name)
        algorithm = AlgorithmFactory.create(
            algorithm_type=step["algorithm_type"],
            tensor_backend=backend,
            tensor_backend_name=tensor_backend_name,
            **step["algorithm_kwargs"],
        )
        algorithms["post"].append((step, backend, algorithm))

    return algorithms


def _process_single_frame_stream(
    *,
    stage_plan: StagePlan,
    algorithms: dict[str, Any],
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
) -> None:
    held: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames
    single_total = max(source_frames, 1)

    while not stop_event.is_set():
        item = _queue_get(decode_queue, stop_event)
        if item is None:
            continue

        if item is _DECODE_END:
            break

        if not isinstance(item, DecodedFrame):
            continue

        frame = item.frame
        for step_index, (_, backend, algorithm) in enumerate(algorithms["single"]):
            frame = _run_single_frame_algorithm(backend, algorithm, frame)
            progress_callbacks[step_index](item.source_index + 1, single_total)

        if held is None:
            held = (item.source_index, frame)
            continue

        held_source_index, held_frame = held
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=held_frame),
            stop_event,
        )
        output_index += 1
        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        held = (item.source_index, frame)

    if held is not None:
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=held[1]),
            stop_event,
        )
        output_index += 1

    _queue_put(
        encode_queue,
        StreamEnd(next_source_frame=source_frames),
        stop_event,
    )
    _queue_put(encode_queue, _ENCODE_END, stop_event)
    del stage_plan


def _process_interpolated_stream(
    *,
    stage_plan: StagePlan,
    algorithms: dict[str, Any],
    progress_callbacks: list[Callable[[int, int], None]],
    source_frames: int,
    resume_output_frames: int,
    decode_queue: queue.Queue[DecodedFrame | object],
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    stop_event: threading.Event,
) -> None:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        raise RuntimeError("Interpolation stage is required for interpolated processing.")

    pre_count = len(stage_plan.pre_steps)
    interpolation_callback = progress_callbacks[pre_count]
    post_callbacks = progress_callbacks[pre_count + 1 :]
    interpolation_backend, interpolation_algorithm = algorithms["interpolation"]
    multi = int(interpolation_step["algorithm_kwargs"].get("multi") or 2)

    previous: tuple[int, np.ndarray] | None = None
    output_index = resume_output_frames
    total_pairs = max(source_frames - 1, 1)

    while not stop_event.is_set():
        item = _queue_get(decode_queue, stop_event)
        if item is None:
            continue

        if item is _DECODE_END:
            break

        if not isinstance(item, DecodedFrame):
            continue

        current_frame = item.frame
        for step_index, (_, backend, algorithm) in enumerate(algorithms["single"]):
            current_frame = _run_single_frame_algorithm(backend, algorithm, current_frame)
            progress_callbacks[step_index](item.source_index + 1, max(source_frames, 1))

        if previous is None:
            previous = (item.source_index, current_frame)
            continue

        prev_source_index, prev_frame = previous
        interpolation_callback(prev_source_index + 1, total_pairs)

        group_frames = [prev_frame]
        prev_tensor = interpolation_backend.numpy_to_tensor(prev_frame)
        current_tensor = interpolation_backend.numpy_to_tensor(current_frame)
        for mid_index in range(1, multi):
            timestep = mid_index / multi
            mid_tensor = interpolation_algorithm.process_frame_pair(prev_tensor, current_tensor, timestep=timestep)
            group_frames.append(interpolation_backend.tensor_to_numpy(mid_tensor))

        for frame in group_frames:
            processed_output = frame
            for callback_index, (_, backend, algorithm) in enumerate(algorithms["post"]):
                processed_output = _run_single_frame_algorithm(backend, algorithm, processed_output)
                post_callbacks[callback_index](output_index + 1, max(stage_plan.total_output_frames, 1))
            _queue_put(
                encode_queue,
                EncodedFrame(output_index=output_index, frame=processed_output),
                stop_event,
            )
            output_index += 1

        _queue_put(
            encode_queue,
            SegmentBoundary(next_source_frame=item.source_index),
            stop_event,
        )
        previous = (item.source_index, current_frame)

    if previous is not None:
        final_frame = previous[1]
        for callback_index, (_, backend, algorithm) in enumerate(algorithms["post"]):
            final_frame = _run_single_frame_algorithm(backend, algorithm, final_frame)
            post_callbacks[callback_index](output_index + 1, max(stage_plan.total_output_frames, 1))
        _queue_put(
            encode_queue,
            EncodedFrame(output_index=output_index, frame=final_frame),
            stop_event,
        )
        output_index += 1

    _queue_put(
        encode_queue,
        StreamEnd(next_source_frame=source_frames),
        stop_event,
    )
    _queue_put(encode_queue, _ENCODE_END, stop_event)


def _run_single_frame_algorithm(backend: Any, algorithm: Any, frame: np.ndarray) -> np.ndarray:
    tensor = backend.numpy_to_tensor(frame)
    processed = algorithm.process_frame(tensor)
    return backend.tensor_to_numpy(processed)


def _queue_put(target_queue: queue.Queue[Any], item: Any, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            target_queue.put(item, timeout=0.1)
            return
        except queue.Full:
            continue


def _queue_put_nowait(target_queue: queue.Queue[Any], item: Any) -> None:
    try:
        target_queue.put_nowait(item)
    except queue.Full:
        pass


def _queue_get(source_queue: queue.Queue[Any], stop_event: threading.Event) -> Any | None:
    while not stop_event.is_set():
        try:
            return source_queue.get(timeout=0.1)
        except queue.Empty:
            continue
    return None


def _finalize_segmented_output(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    signature: str,
    completed_output_frames: int,
    total_output_frames: int,
    strict_total_frames: bool,
) -> str:
    del signature
    completed_segments = manifest.read_completed_segments()
    segment_paths = [str(manifest.sidecar_dir / record.path) for record in completed_segments]
    if strict_total_frames and completed_output_frames != total_output_frames:
        raise RuntimeError(
            f"Temporary segments are incomplete: expected {total_output_frames} output frames, "
            f"got {completed_output_frames}."
        )
    if not segment_paths:
        raise RuntimeError("No completed temporary segments were found for finalization.")

    extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
    concat_path = manifest.concat_temp_path(extension)
    ffmpeg.concat_videos(segment_paths, concat_path)

    keep_audio = bool(encode_config.get("keepAudio", True))
    if keep_audio and ffmpeg.has_audio(input_path):
        audio_path = ffmpeg.extract_audio(input_path, str(manifest.sidecar_dir / "source_audio.aac"))
        if audio_path:
            final_output = ffmpeg.merge_audio(concat_path, audio_path, output_path)
            Path(audio_path).unlink(missing_ok=True)
            Path(concat_path).unlink(missing_ok=True)
            return final_output

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    os.replace(concat_path, output_path)
    return output_path
