"""Pure stage-worker planning helpers for parent-side streaming execution."""

from __future__ import annotations

from dataclasses import dataclass

from app.generated.stage_worker_contracts import StageWorkerConfig
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import StagePlan
from app.planning.stage_projection import StageProjection
from app.planning.temporal_slicing import plan_temporal_slices
from app.processing.streaming.stage_rules import stage_tensor_backend_name
from app.processing.streaming.stage_worker_config import build_stage_worker_step


@dataclass(frozen=True, slots=True)
class StageChunkPlan:
    """One bounded input slice for a single algorithm stage."""

    input_start_frame: int
    input_frame_count: int
    logical_input_frame_count: int
    raw_output_frame_count: int
    written_output_frame_count: int
    skip_output_frames: int = 0
    output_frame_offset: int = 0
    logical_start_frame: int | None = None


def build_stage_worker_plans(
    *,
    stage_plan: StagePlan,
    source_frame_count: int,
) -> list[StageWorkerConfig]:
    """Build sequential stage-worker configs from a resolved ``StagePlan``."""
    steps = stage_plan.processing_steps
    configs: list[StageWorkerConfig] = []
    projected_stages = stage_plan.slice_stages(source_frame_count)
    for projected_stage in projected_stages:
        index = projected_stage.position
        step = projected_stage.step
        input_frame_count = projected_stage.input_frames
        input_width = projected_stage.input_width
        input_height = projected_stage.input_height
        output_width = projected_stage.output_width
        output_height = projected_stage.output_height
        output_frame_count = projected_stage.output_frames
        configs.append(
            StageWorkerConfig(
                stage=build_stage_worker_step(step),
                stage_index=index,
                stage_total=len(steps),
                stage_name=step.stage_name or step.algorithm_type,
                input_width=input_width,
                input_height=input_height,
                output_width=output_width,
                output_height=output_height,
                input_frame_count=input_frame_count,
                tensor_backend_name=stage_tensor_backend_name(step),
                output_frame_count=output_frame_count,
                output_frame_offset=0,
            )
        )
    return configs


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
    context_frames = step.descriptor.temporal_context_frames
    if context_frames > 0:
        for temporal_slice in plan_temporal_slices(
            total_frames,
            logical_chunk_frames=chunk_size,
            context_frames=context_frames,
        ):
            chunks.append(
                StageChunkPlan(
                    input_start_frame=temporal_slice.read_start,
                    input_frame_count=temporal_slice.read_count,
                    logical_input_frame_count=temporal_slice.logical_count,
                    raw_output_frame_count=temporal_slice.logical_count,
                    written_output_frame_count=temporal_slice.logical_count,
                    output_frame_offset=temporal_slice.output_offset,
                    logical_start_frame=temporal_slice.logical_start,
                )
            )
        return chunks

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
                    logical_start_frame=start,
                )
            )
        return chunks

    for start in range(0, total_frames, chunk_size):
        logical_count = min(chunk_size, total_frames - start)
        has_lookahead = start + logical_count < total_frames
        read_count = logical_count + (1 if has_lookahead else 0)
        raw_output_count = StageProjection.project_frame_count(step, read_count)
        skip_output_frames = 1 if start > 0 and raw_output_count > 0 else 0
        chunks.append(
            StageChunkPlan(
                input_start_frame=start,
                input_frame_count=read_count,
                logical_input_frame_count=logical_count,
                raw_output_frame_count=raw_output_count,
                written_output_frame_count=max(raw_output_count - skip_output_frames, 0),
                skip_output_frames=skip_output_frames,
                logical_start_frame=start,
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

    multi = int(stage_plan.interpolation_step.algorithm_kwargs["multi"])
    for next_source_frame in range(start_source_frame + 1, source_frames):
        emitted_count = (next_source_frame - start_source_frame) * multi
        schedule[emitted_count] = next_source_frame
    return schedule


__all__ = [
    "StageChunkPlan",
    "boundary_schedule_for_stage_plan",
    "build_stage_chunk_plans",
    "build_stage_worker_plans",
]
