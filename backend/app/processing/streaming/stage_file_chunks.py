"""Chunk execution helpers for file-backed segmented stage pipelines."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.planning import ProcessingStep
from app.planning.manifest import ResumeState, SegmentManifest
from app.processing.streaming.stage_file_chunk_progress import (
    chunk_progress_adapter,
    stage_chunk_output_start,
)
from app.processing.streaming.stage_file_chunk_runtime import run_stage_chunk_to_file
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_rules import stage_progress_total
from app.processing.streaming.worker_plans import build_stage_chunk_plans


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


__all__ = [
    "chunk_progress_adapter",
    "run_single_stage_file_chunks",
    "run_stage_chunk_to_file",
    "stage_chunk_output_start",
]
