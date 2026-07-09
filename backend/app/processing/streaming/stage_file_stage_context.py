"""Per-stage context rules for file-backed stage pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.planning import ProcessingStep
from app.planning.manifest import ResumeState, SegmentManifest
from app.processing.streaming.stage_file_rules import empty_resume_state, safe_stage_name, stage_signature


@dataclass(slots=True)
class StageFileStageContext:
    manifest: SegmentManifest
    output_path: str
    resume_state: ResumeState
    start_frame: int
    chunk_start_index: int
    encode_output_fps: float | None
    encode_config: dict[str, Any]


def build_stage_file_stage_context(
    *,
    is_final_stage: bool,
    stage_position: int,
    step: ProcessingStep,
    stage_root: Path,
    current_path: str,
    current_frame_count: int,
    output_path: str,
    manifest: SegmentManifest,
    resume_state: ResumeState,
    encode_config: dict[str, Any],
    segment_frames: int,
    output_fps: float | None,
) -> StageFileStageContext:
    if is_final_stage:
        return StageFileStageContext(
            manifest=manifest,
            output_path=output_path,
            resume_state=resume_state,
            start_frame=min(int(resume_state.start_source_frame), int(current_frame_count)),
            chunk_start_index=len(resume_state.completed_segments) + 1,
            encode_output_fps=output_fps,
            encode_config=encode_config,
        )

    stage_output_path = str(stage_root / f"stage-{stage_position:02d}-{safe_stage_name(step)}.mp4")
    stage_manifest = SegmentManifest(stage_output_path)
    stage_manifest.prepare(
        stage_signature(stage_position, step, current_path, stage_output_path),
        {
            "input_path": current_path,
            "output_path": stage_output_path,
            "stage": step.to_jsonable(),
            "segmentFrames": max(1, int(segment_frames)),
        },
        mode="force-fresh",
    )
    return StageFileStageContext(
        manifest=stage_manifest,
        output_path=stage_output_path,
        resume_state=empty_resume_state(),
        start_frame=0,
        chunk_start_index=1,
        encode_output_fps=None,
        encode_config={**encode_config, "keepAudio": False},
    )


__all__ = ["build_stage_file_stage_context"]
