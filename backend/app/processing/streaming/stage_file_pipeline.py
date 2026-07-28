"""File-backed segmented stage-worker pipeline helpers."""

from __future__ import annotations

from app.processing.streaming.encoder_finalization import finalize_segmented_output
from app.processing.streaming.pipeline_context import StreamingPipelineContext
from app.processing.streaming.stage_file_chunks import run_single_stage_file_chunks
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from app.processing.streaming.stage_file_stage_context import build_stage_file_stage_context
from app.processing.streaming.stage_rules import (
    stage_output_dimensions,
    stage_tensor_backend_name,
)


def run_stage_file_pipeline(
    *,
    context: StreamingPipelineContext,
) -> int:
    """Run each algorithm stage as segmented files instead of one rawvideo chain."""
    stage_plan = context.preflight.stage_plan
    steps = stage_plan.steps
    if not steps:
        raise RuntimeError("Stage file pipeline requires at least one processing stage.")

    stage_root = context.manifest.workspace.stages_dir
    stage_root.mkdir(parents=True, exist_ok=True)

    current_path = context.input_path
    current_width = context.preflight.video_info.width
    current_height = context.preflight.video_info.height
    projected_stages = stage_plan.projection.stages(
        source_frames=context.preflight.video_info.source_frames,
        source_fps=context.preflight.video_info.source_fps,
    )

    for projected_stage in projected_stages:
        stage_position = projected_stage.position
        step = projected_stage.step
        is_final_stage = stage_position == len(steps)
        current_frame_count = projected_stage.input_frames
        output_width, output_height = stage_output_dimensions(
            step,
            input_width=current_width,
            input_height=current_height,
        )
        stage_output_frames = projected_stage.output_frames
        stage_fps = float(projected_stage.output_fps)

        stage_context = build_stage_file_stage_context(
            is_final_stage=is_final_stage,
            stage_position=stage_position,
            step=step,
            stage_root=stage_root,
            current_path=current_path,
            current_frame_count=current_frame_count,
            output_path=context.output_path,
            manifest=context.manifest,
            resume_state=context.resume_state,
            encode_config=context.encode_config,
            segment_frames=context.preflight.segment_frames,
            output_fps=context.output_fps,
        )

        runtime_config = StageFileRuntimeConfig(
            ffmpeg=context.ffmpeg,
            input_path=current_path,
            decode_config=context.decode_config,
            encode_config=stage_context.encode_config,
            step=step,
            stage_index=stage_position,
            stage_total=len(steps),
            tensor_backend_name=stage_tensor_backend_name(step),
            progress_callback=context.progress_callbacks[stage_position - 1]
            if stage_position - 1 < len(context.progress_callbacks)
            else None,
            input_width=current_width,
            input_height=current_height,
            output_width=output_width,
            output_height=output_height,
            output_fps=stage_fps,
            encode_output_fps=stage_context.encode_output_fps,
            metrics=context.metrics,
        )
        completed_frames = run_single_stage_file_chunks(
            config=runtime_config,
            manifest=stage_context.manifest,
            resume_state=stage_context.resume_state,
            start_frame=stage_context.start_frame,
            start_chunk_index=stage_context.chunk_start_index,
            segment_frames=context.preflight.segment_frames,
            input_frame_count=current_frame_count,
            output_frame_count=stage_output_frames,
        )

        if is_final_stage:
            return completed_frames

        finalize_segmented_output(
            ffmpeg=context.ffmpeg,
            input_path=current_path,
            output_path=stage_context.output_path,
            encode_config=stage_context.encode_config,
            manifest=stage_context.manifest,
            completed_output_frames=completed_frames,
            total_output_frames=stage_output_frames,
            strict_total_frames=True,
        )
        stage_context.manifest.workspace.cleanup()
        current_path = stage_context.output_path
        current_width = output_width
        current_height = output_height


__all__ = [
    "run_stage_file_pipeline",
]
