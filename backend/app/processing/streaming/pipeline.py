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
    ProcessingStepInput,
    ResumeMode,
    ResumeState,
    SegmentManifest,
    StagePlan,
    build_signature,
    build_stage_plan,
    normalize_processing_steps,
    processing_steps_to_jsonable,
    resolve_video_info,
)
from app.processing.streaming.encoder import _encoder_worker, _finalize_segmented_output
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
)
from app.processing.streaming.worker_pipeline import run_stage_file_pipeline, run_stage_worker_pipeline
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
    processing_steps: list[ProcessingStepInput],
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    output_fps: float | None = None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None = None,
    resume_mode: ResumeMode = "auto",
    metrics: PipelineMetrics | None = None,
) -> dict[str, Any]:
    """Process a video without writing temporary frames to disk."""
    if metrics is None:
        # Standalone caller (tests, smoke scripts) — keep the call site
        # simple by self-provisioning metrics that nobody reads.
        metrics = PipelineMetrics()
    resolved_steps = normalize_processing_steps(processing_steps)
    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        resolved_steps,
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
        processing_steps=resolved_steps,
        video_info=video_info,
    )
    config_snapshot = _build_config_snapshot(
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=resolved_steps,
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
    use_stage_file_pipeline = _should_use_stage_file_pipeline(stage_plan)
    resume_source_frames = (
        _stage_file_resume_source_frames(stage_plan, int(video_info["source_frames"]))
        if use_stage_file_pipeline
        else int(video_info["source_frames"])
    )
    output_width, output_height = _resolved_output_dimensions(
        video_info=video_info,
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
    )

    if resume_state.start_source_frame >= resume_source_frames:
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
            metrics=metrics,
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
    processing_steps: list[ProcessingStepInput],
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
        "processing_steps": processing_steps_to_jsonable(processing_steps),
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
    metrics: PipelineMetrics,
) -> int:
    if _should_use_stage_file_pipeline(stage_plan):
        _emit_resume_status_event(
            resume_state=resume_state,
            total_output_frames=stage_plan.total_encoded_frames,
        )
        return run_stage_file_pipeline(
            ffmpeg=ffmpeg,
            input_path=input_path,
            decode_config=decode_config,
            encode_config=encode_config,
            manifest=manifest,
            stage_plan=stage_plan,
            tensor_backend_name=tensor_backend_name,
            progress_callbacks=progress_callbacks,
            video_info=video_info,
            resume_state=resume_state,
            segment_frames=segment_frames,
            output_path=output_path,
            output_fps=output_fps,
            metrics=metrics,
        )

    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    encoder_thread = threading.Thread(
        target=_encoder_worker,
        name="vp-encoder",
        kwargs={
            "decode_queue": queue.Queue(maxsize=1),
            "encode_queue": encode_queue,
            "error_queue": error_queue,
            "stop_event": stop_event,
            "metrics": metrics,
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
    )

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

    encoder_thread.start()
    run_stage_worker_pipeline(
        ffmpeg=ffmpeg,
        input_path=input_path,
        decode_config=decode_config,
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
        progress_callbacks=progress_callbacks,
        video_info=video_info,
        resume_state=resume_state,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=metrics,
    )
    encoder_thread.join()

    if not error_queue.empty():
        raise error_queue.get()

    del signature
    completed_segments = manifest.read_completed_segments()
    return sum(segment.frame_count for segment in completed_segments)


def _should_use_stage_file_pipeline(stage_plan: StagePlan) -> bool:
    for step in _stage_steps(stage_plan):
        if step.algorithm_type == "frame_interpolation":
            return True
        if step.algorithm_type != "super_resolution":
            continue
        try:
            from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS
        except Exception:
            continue
        if str(step.algorithm_kwargs.get("sr_algorithm") or "") in PADDLEGAN_VSR_SPECS:
            return True
    return False


def _stage_file_resume_source_frames(stage_plan: StagePlan, source_frames: int) -> int:
    """Return the source-frame domain used by the final staged manifest."""
    current_frames = max(int(source_frames), 0)
    steps = _stage_steps(stage_plan)
    for step in steps[:-1]:
        if step.algorithm_type != "frame_interpolation" or current_frames < 2:
            continue
        multi = int(step.algorithm_kwargs.get("multi") or 2)
        current_frames = current_frames + (current_frames - 1) * (multi - 1)
    return current_frames


def _stage_steps(stage_plan: StagePlan) -> list[Any]:
    return [
        *stage_plan.pre_steps,
        *([stage_plan.interpolation_step] if stage_plan.interpolation_step else []),
        *stage_plan.post_steps,
    ]


def _resolved_stream_fps(source_fps: float, stage_plan: StagePlan) -> float:
    interpolation_step = stage_plan.interpolation_step
    if interpolation_step is None:
        return source_fps
    multi = int(interpolation_step.algorithm_kwargs.get("multi") or 2)
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
    from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS

    for step in [*stage_plan.pre_steps, *stage_plan.post_steps]:
        if step.algorithm_type != "super_resolution":
            continue
        kwargs = step.algorithm_kwargs
        sr_algorithm = str(kwargs.get("sr_algorithm") or "")
        is_paddlegan_vsr = sr_algorithm in PADDLEGAN_VSR_SPECS
        if not is_paddlegan_vsr and not kwargs.get("onnx_model"):
            continue
        scale_factor = float(kwargs.get("scale_factor") or 1.0)
        width = max(1, int(round(width * scale_factor)))
        height = max(1, int(round(height * scale_factor)))

    del tensor_backend_name
    return width, height
