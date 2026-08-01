"""Resume and finalization lifecycle helpers for streaming pipeline entry."""

from __future__ import annotations

from typing import Any

from app.errors.process import ResumeConflictError
from app.planning.manifest import ResumeState, SegmentManifest
from app.planning.resume_policy import ResumeMode
from app.processing.streaming.encoder_finalization import finalize_segmented_output
from app.processing.streaming.pipeline_context import StreamingPipelineContext
from app.processing.execution_result import ExecutionResult


def prepare_streaming_manifest(
    *,
    manifest: SegmentManifest,
    signature: str,
    config_snapshot: dict[str, Any],
    resume_mode: ResumeMode,
) -> tuple[SegmentManifest, ResumeState]:
    decision = manifest.prepare(signature, config_snapshot, mode=resume_mode)
    if decision.kind == "conflict_final_exists":
        raise ResumeConflictError(
            output_path=str(manifest.workspace.output_path),
            completed_chunks=len(decision.state.completed_segments),
            completed_output_frames=decision.state.completed_output_frames,
            sidecar_signature_match=decision.sidecar_signature_match,
        )
    return manifest, decision.state


def finalize_streaming_output(
    *,
    context: StreamingPipelineContext,
    completed_output_frames: int,
) -> ExecutionResult:
    finalize_segmented_output(
        ffmpeg=context.ffmpeg,
        input_path=context.input_path,
        output_path=context.output_path,
        encode_config=context.encode_config,
        manifest=context.manifest,
        completed_output_frames=completed_output_frames,
        total_output_frames=context.preflight.stage_plan.total_encoded_frames,
        strict_total_frames=context.preflight.stage_plan.encoder_fps_override is None,
        source_has_audio=context.preflight.stage_plan.source.has_audio,
    )

    context.manifest.workspace.cleanup()
    processed_frames = context.ffmpeg.get_frame_count(context.output_path)
    return ExecutionResult(
        output_path=context.output_path,
        processed_frames=processed_frames or completed_output_frames,
    )
