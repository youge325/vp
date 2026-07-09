"""Resume and finalization lifecycle helpers for streaming pipeline entry."""

from __future__ import annotations

from typing import Any

from app.errors import ResumeConflictError
from app.planning import ResumeMode, ResumeState, SegmentManifest
from app.processing.streaming.encoder_finalization import finalize_segmented_output
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.logger import get_logger

logger = get_logger(__name__)


def prepare_streaming_manifest(
    *,
    output_path: str,
    signature: str,
    config_snapshot: dict[str, Any],
    resume_mode: ResumeMode,
) -> tuple[SegmentManifest, ResumeState]:
    manifest = SegmentManifest(output_path)
    decision = manifest.prepare(signature, config_snapshot, mode=resume_mode)
    if decision.kind == "conflict_final_exists":
        raise ResumeConflictError(
            output_path=str(manifest.output_path),
            completed_chunks=len(decision.state.completed_segments),
            completed_output_frames=decision.state.completed_output_frames,
            sidecar_signature_match=decision.sidecar_signature_match,
        )
    return manifest, decision.state


def emit_resume_status_event(*, resume_state: ResumeState, total_output_frames: int) -> None:
    """Emit a structured resume_status JSON line consumed by the Tauri host."""
    try:
        ndjson.resume_status(
            resumed=resume_state.completed_output_frames > 0,
            completed_chunks=len(resume_state.completed_segments),
            completed_output_frames=resume_state.completed_output_frames,
            start_source_frame=resume_state.start_source_frame,
            total_output_frames=total_output_frames,
        )
    except Exception:  # pragma: no cover - never let telemetry break the pipeline
        logger.exception("Failed to emit resume_status event")


def finalize_streaming_output(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    completed_output_frames: int,
    total_output_frames: int,
    strict_total_frames: bool,
) -> dict[str, Any]:
    final_output = finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        encode_config=encode_config,
        manifest=manifest,
        completed_output_frames=completed_output_frames,
        total_output_frames=total_output_frames,
        strict_total_frames=strict_total_frames,
    )

    manifest.cleanup()
    processed_frames = ffmpeg.get_frame_count(final_output)
    return {
        "output_path": final_output,
        "processed_frames": processed_frames or completed_output_frames,
        "audio_merged": bool(encode_config.get("keepAudio", True)),
    }
