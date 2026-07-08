"""Raw pipeline queue/thread runtime."""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_completion import finish_raw_pipeline_runtime
from app.processing.streaming.pipeline_raw_encoder import start_raw_encoder_thread
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd
from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline
from app.utils.ffmpeg import FFmpegWrapper

StageWorkerRunner = Callable[..., None]


def run_raw_pipeline_runtime(
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
    stream_fps: float,
    resume_state: ResumeState,
    segment_frames: int,
    output_path: str,
    output_fps: float | None,
    encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
    metrics: PipelineMetrics,
    stage_worker_runner: StageWorkerRunner | None = None,
) -> int:
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object] = queue.Queue(maxsize=8)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    encoder_thread = start_raw_encoder_thread(
        ffmpeg=ffmpeg,
        encode_config=encode_config,
        manifest=manifest,
        signature=signature,
        output_width=output_width,
        output_height=output_height,
        stream_fps=stream_fps,
        output_fps=output_fps,
        segment_frames=segment_frames,
        resume_state=resume_state,
        output_path=output_path,
        encode_progress_callback=encode_progress_callback,
        metrics=metrics,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
    )
    runner = stage_worker_runner or run_stage_worker_pipeline
    runner(
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
    return finish_raw_pipeline_runtime(
        encoder_thread=encoder_thread,
        error_queue=error_queue,
        manifest=manifest,
    )


__all__ = ["StageWorkerRunner", "run_raw_pipeline_runtime"]
