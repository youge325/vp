"""Rawvideo worker-chain runtime for streaming pipeline execution."""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.encoder import _encoder_worker
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_rules import resolved_stream_fps
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd
from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline
from app.utils.ffmpeg import FFmpegWrapper

StageWorkerRunner = Callable[..., None]


def run_raw_streaming_pipeline(
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
    stage_worker_runner: StageWorkerRunner = run_stage_worker_pipeline,
) -> int:
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
            "fps": resolved_stream_fps(video_info["source_fps"], stage_plan),
            "output_fps": output_fps,
            "segment_frames": segment_frames,
            "resume_state": resume_state,
            "output_path": output_path,
            "encode_progress_callback": encode_progress_callback,
        },
        daemon=True,
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
    stage_worker_runner(
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

    completed_segments = manifest.read_completed_segments()
    return sum(segment.frame_count for segment in completed_segments)


__all__ = ["run_raw_streaming_pipeline"]
