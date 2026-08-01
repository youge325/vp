"""Stage-file/raw dispatch for streaming pipeline execution."""

from __future__ import annotations

from app.processing.streaming.pipeline_context import StreamingPipelineContext
from app.processing.streaming.pipeline_raw import run_raw_streaming_pipeline
from app.processing.streaming.stage_file_pipeline import run_stage_file_pipeline


def run_streaming_pipeline(
    *,
    context: StreamingPipelineContext,
) -> int:
    context.resume_status_sink(
        context.resume_state,
        context.preflight.stage_plan.total_encoded_frames,
    )

    if context.preflight.stage_plan.requires_file_pipeline:
        return run_stage_file_pipeline(context=context)

    return run_raw_streaming_pipeline(context=context)


__all__ = ["run_streaming_pipeline"]
