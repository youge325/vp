"""Chunk execution helpers for file-backed segmented stage pipelines."""

from __future__ import annotations

import os
from pathlib import Path

from app.planning.manifest import ResumeState, SegmentManifest
from app.processing.streaming import stage_file_chunk_runtime
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from app.processing.streaming.stage_rules import stage_progress_total
from app.processing.streaming.worker_plans import build_stage_chunk_plans


def run_single_stage_file_chunks(
    *,
    config: StageFileRuntimeConfig,
    manifest: SegmentManifest,
    input_frame_count: int,
    output_frame_count: int,
    resume_state: ResumeState,
    start_frame: int,
    start_chunk_index: int,
    segment_frames: int,
) -> int:
    extension = os.path.splitext(str(manifest.workspace.output_path))[1] or (
        f".{config.encode_config.get('container') or 'mp4'}"
    )
    chunks = [
        chunk
        for chunk in build_stage_chunk_plans(
            config.step,
            input_frame_count=input_frame_count,
            segment_frames=segment_frames,
        )
        if chunk.input_start_frame >= start_frame
    ]
    if not chunks:
        return int(resume_state.completed_output_frames)

    output_start = int(resume_state.completed_output_frames)
    chunk_index = int(start_chunk_index)
    completed_output_frames = output_start
    stage_total_frames = stage_progress_total(config.step, input_frame_count, output_frame_count)

    for chunk in chunks:
        if chunk.written_output_frame_count <= 0:
            continue
        tmp_path = manifest.workspace.chunk_tmp_path(extension, index=chunk_index)
        actual_written = stage_file_chunk_runtime.run_stage_chunk_to_file(
            config=config,
            output_path=tmp_path,
            chunk=chunk,
            stage_total_frames=stage_total_frames,
        )
        if actual_written <= 0:
            Path(tmp_path).unlink(missing_ok=True)
            continue
        manifest.workspace.finalize_chunk(
            tmp_path,
            index=chunk_index,
            start_output_frame=completed_output_frames,
            end_output_frame=completed_output_frames + actual_written - 1,
            next_source_frame=chunk.input_start_frame + chunk.logical_input_frame_count,
        )
        completed_output_frames += actual_written
        chunk_index += 1

    return completed_output_frames


__all__ = ["run_single_stage_file_chunks"]
