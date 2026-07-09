"""File-backed segmented stage-worker pipeline helpers."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from app.planning import StagePlan
from app.processing.streaming.encoder_finalization import finalize_segmented_output
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_chunks import run_single_stage_file_chunks
from app.processing.streaming.stage_file_stage_context import build_stage_file_stage_context
from app.processing.streaming.stage_rules import (
    ordered_steps,
    stage_output_dimensions,
    stage_output_fps,
    stage_output_frame_count,
    stage_tensor_backend_name,
)

if TYPE_CHECKING:
    from app.planning.manifest import ResumeState, SegmentManifest


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

        stage_context = build_stage_file_stage_context(
            is_final_stage=is_final_stage,
            stage_position=stage_position,
            step=step,
            stage_root=stage_root,
            current_path=current_path,
            current_frame_count=current_frame_count,
            output_path=output_path,
            manifest=manifest,
            resume_state=resume_state,
            encode_config=encode_config,
            segment_frames=segment_frames,
            output_fps=output_fps,
        )

        completed_frames = run_single_stage_file_chunks(
            ffmpeg=ffmpeg,
            input_path=current_path,
            decode_config=decode_config,
            encode_config=stage_context.encode_config,
            manifest=stage_context.manifest,
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
            output_fps=stage_fps,
            encode_output_fps=stage_context.encode_output_fps,
            resume_state=stage_context.resume_state,
            start_frame=stage_context.start_frame,
            start_chunk_index=stage_context.chunk_start_index,
            segment_frames=segment_frames,
            metrics=metrics,
            python_executable=python_executable or sys.executable,
        )

        if is_final_stage:
            return completed_frames

        finalized = finalize_segmented_output(
            ffmpeg=ffmpeg,
            input_path=current_path,
            output_path=stage_context.output_path,
            encode_config=stage_context.encode_config,
            manifest=stage_context.manifest,
            completed_output_frames=completed_frames,
            total_output_frames=stage_output_frames,
            strict_total_frames=True,
        )
        stage_context.manifest.cleanup()
        current_path = finalized
        current_width = output_width
        current_height = output_height
        current_fps = stage_fps
        current_frame_count = stage_output_frames

    return completed_frames


__all__ = [
    "run_stage_file_pipeline",
]
