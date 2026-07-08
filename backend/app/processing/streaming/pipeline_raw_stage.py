"""Raw pipeline stage-worker invocation."""

from __future__ import annotations

from typing import Any, Callable

from app.planning import ResumeState, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_state import RawPipelineState
from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline
from app.utils.ffmpeg import FFmpegWrapper


def run_raw_stage_worker(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    decode_config: dict[str, Any],
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Callable[[int, int], None]],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    metrics: PipelineMetrics,
    state: RawPipelineState,
    stage_worker_runner: Callable[..., None] | None = None,
) -> None:
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
        encode_queue=state.encode_queue,
        error_queue=state.error_queue,
        stop_event=state.stop_event,
        metrics=metrics,
    )


__all__ = ["run_raw_stage_worker"]
