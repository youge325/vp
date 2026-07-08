"""Pure stage-worker planning helpers for parent-side streaming execution."""

from __future__ import annotations

from dataclasses import dataclass

from app.planning import ProcessingStep, StagePlan
from app.processing.streaming.stage_rules import (
    ordered_steps,
    stage_output_dimensions,
    stage_output_frame_count,
    stage_tensor_backend_name,
)
from app.processing.streaming.stage_worker import StageWorkerConfig


@dataclass(frozen=True, slots=True)
class StageWorkerPlan:
    """Parent-side plan for one stage-worker process."""

    config: StageWorkerConfig
    output_frame_count: int


@dataclass(frozen=True, slots=True)
class StageChunkPlan:
    """One bounded input slice for a single algorithm stage."""

    input_start_frame: int
    input_frame_count: int
    logical_input_frame_count: int
    raw_output_frame_count: int
    written_output_frame_count: int
    skip_output_frames: int = 0


def build_stage_worker_plans(
    *,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    source_width: int,
    source_height: int,
    source_frame_count: int,
) -> list[StageWorkerPlan]:
    """Build sequential stage-worker configs from a resolved ``StagePlan``."""
    steps = ordered_steps(stage_plan)
    plans: list[StageWorkerPlan] = []
    input_width = source_width
    input_height = source_height
    input_frame_count = source_frame_count

    for index, step in enumerate(steps, start=1):
        output_width, output_height = stage_output_dimensions(
            step,
            input_width=input_width,
            input_height=input_height,
        )
        output_frame_count = stage_output_frame_count(step, input_frame_count)
        plans.append(
            StageWorkerPlan(
                config=StageWorkerConfig(
                    stage=step,
                    stage_index=index,
                    stage_total=len(steps),
                    stage_name=step.stage_name or step.algorithm_type,
                    input_width=input_width,
                    input_height=input_height,
                    output_width=output_width,
                    output_height=output_height,
                    input_frame_count=input_frame_count,
                    tensor_backend_name=stage_tensor_backend_name(step, tensor_backend_name),
                    output_frame_count=output_frame_count,
                ),
                output_frame_count=output_frame_count,
            )
        )
        input_width = output_width
        input_height = output_height
        input_frame_count = output_frame_count

    return plans


def build_stage_chunk_plans(
    step: ProcessingStep,
    *,
    input_frame_count: int,
    segment_frames: int,
) -> list[StageChunkPlan]:
    """Split one stage into bounded chunks.

    Interpolation chunks read one lookahead frame except on the final chunk so
    the boundary pair is processed; chunks after the first skip the duplicate
    first original frame from their output.
    """
    total_frames = max(int(input_frame_count), 0)
    chunk_size = max(int(segment_frames), 1)
    if total_frames <= 0:
        return []

    chunks: list[StageChunkPlan] = []
    if step.algorithm_type != "frame_interpolation":
        for start in range(0, total_frames, chunk_size):
            count = min(chunk_size, total_frames - start)
            chunks.append(
                StageChunkPlan(
                    input_start_frame=start,
                    input_frame_count=count,
                    logical_input_frame_count=count,
                    raw_output_frame_count=count,
                    written_output_frame_count=count,
                )
            )
        return chunks

    for start in range(0, total_frames, chunk_size):
        logical_count = min(chunk_size, total_frames - start)
        has_lookahead = start + logical_count < total_frames
        read_count = logical_count + (1 if has_lookahead else 0)
        raw_output_count = stage_output_frame_count(step, read_count)
        skip_output_frames = 1 if start > 0 and raw_output_count > 0 else 0
        chunks.append(
            StageChunkPlan(
                input_start_frame=start,
                input_frame_count=read_count,
                logical_input_frame_count=logical_count,
                raw_output_frame_count=raw_output_count,
                written_output_frame_count=max(raw_output_count - skip_output_frames, 0),
                skip_output_frames=skip_output_frames,
            )
        )
    return chunks


def boundary_schedule_for_stage_plan(
    *,
    stage_plan: StagePlan,
    start_source_frame: int,
    source_frames: int,
) -> dict[int, int]:
    """Map emitted-frame counts to ``next_source_frame`` segment boundaries."""
    if start_source_frame >= source_frames:
        return {}
    schedule: dict[int, int] = {}
    if stage_plan.interpolation_step is None:
        for next_source_frame in range(start_source_frame + 1, source_frames):
            emitted_count = next_source_frame - start_source_frame
            schedule[emitted_count] = next_source_frame
        return schedule

    multi = int(stage_plan.interpolation_step.algorithm_kwargs.get("multi") or 2)
    for next_source_frame in range(start_source_frame + 1, source_frames):
        emitted_count = (next_source_frame - start_source_frame) * multi
        schedule[emitted_count] = next_source_frame
    return schedule


__all__ = [
    "StageChunkPlan",
    "StageWorkerPlan",
    "boundary_schedule_for_stage_plan",
    "build_stage_chunk_plans",
    "build_stage_worker_plans",
]
