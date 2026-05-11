"""Streaming pipeline orchestrator.

Builds the stage plan + resume signature, runs the decode/process/encode
threads through :func:`_run_streaming_pipeline`, and finalizes the
segmented output. Public entry point: :func:`process_video_streaming`.
"""

from __future__ import annotations

import os
import queue
import threading
from typing import Any, Callable

from app.errors import ResumeConflictError
from app.planning import (
    ResumeMode,
    ResumeState,
    SegmentManifest,
    StagePlan,
    build_signature,
    build_stage_plan,
    resolve_video_info,
)
from app.processing.streaming.decoder import _decoder_worker
from app.processing.streaming.encoder import _encoder_worker, _finalize_segmented_output
from app.processing.streaming.processor import _processor_worker
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
)
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
    try:
        ndjson.resume_status(
            resumed=resume_state.completed_output_frames > 0,
            completed_chunks=len(resume_state.completed_segments),
            completed_output_frames=resume_state.completed_output_frames,
            start_source_frame=resume_state.start_source_frame,
            total_output_frames=total_output_frames,
        )
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
