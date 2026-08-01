"""Pipeline execution and terminal NDJSON for ``cmd_process``.

收静态运行计划和观察者后,选择 streaming pipeline 或
fast-path FFmpeg transcode 跑流水线，然后把结果格式化成 typed ``ndjson.emit``。
"""

from __future__ import annotations

import time
from pathlib import Path

from app.errors.process import ResumeConflictError
from app.generated.contracts import TaskCompletedPayload
from app.generated.protocol_constants import BackendEnvelopeType
from app.planning.resume_policy import decide_output_action
from app.ports.media import MediaRuntimePort
from app.processing.streaming.pipeline import process_video_streaming
from app.processing.execution_result import ExecutionResult
from app.protocol.emitter import ndjson

from app.cli.commands._pipeline_preparation import PreparedRun
from app.cli.commands._process_planning import RunObservers
from app.cli.runtime_configs import runtime_config_sections


def _resolve_processed_frame_count(ffmpeg: MediaRuntimePort, output_path: str, fallback: int) -> int:
    try:
        return ffmpeg.get_frame_count(output_path) or fallback
    except Exception:  # pragma: no cover - defensive CLI reporting
        return fallback


def _enforce_format_conversion_resume_mode(*, output_path: str, resume_mode: str) -> None:
    """Apply resume_mode semantics for the format-conversion fast path.

    The streaming pipeline owns its own conflict logic via ``SegmentManifest``;
    format-only conversions skip the sidecar entirely, so they need a
    miniature equivalent here so a stale output is not silently overwritten.
    """
    target = Path(output_path)
    action = decide_output_action(
        final_exists=target.exists(),
        sidecar_exists=False,
        signature_match=False,
        has_progress=False,
        mode=resume_mode,
    )
    if action == "fresh" and not target.exists():
        return
    if action == "fresh":
        target.unlink(missing_ok=True)
        return
    raise ResumeConflictError(
        output_path=str(target.resolve()),
        completed_chunks=0,
        completed_output_frames=0,
        sidecar_signature_match=False,
    )


def _run_streaming(
    *,
    ffmpeg: MediaRuntimePort,
    input_path: str,
    prepared: PreparedRun,
    observers: RunObservers,
    resume_mode: str,
) -> ExecutionResult:
    sections = runtime_config_sections(prepared.runtime_configs)
    return process_video_streaming(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=prepared.output_path,
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        preflight=prepared.preflight,
        progress_callbacks=list(observers.progress_callbacks),
        encode_progress_callback=observers.progress_reporter.update,
        resume_mode=resume_mode,
        metrics=observers.metrics,
        manifest_factory=observers.manifest_factory,
        resume_status_sink=observers.resume_status_sink,
        worker_log_sink=observers.worker_log_sink,
    )


def _run_format_conversion(
    *,
    ffmpeg: MediaRuntimePort,
    input_path: str,
    prepared: PreparedRun,
    observers: RunObservers,
    resume_mode: str,
) -> ExecutionResult:
    sections = runtime_config_sections(prepared.runtime_configs)
    decode_config = sections["decode"]
    encode_config = sections["encode"]
    _enforce_format_conversion_resume_mode(output_path=prepared.output_path, resume_mode=resume_mode)
    ffmpeg.transcode_video(
        input_path=input_path,
        output_path=prepared.output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        output_fps=prepared.final_output_fps,
        progress_callback=observers.progress_reporter.update,
    )
    return ExecutionResult(
        output_path=prepared.output_path,
        processed_frames=_resolve_processed_frame_count(
            ffmpeg,
            prepared.output_path,
            prepared.expected_output_frames,
        ),
    )


def execute_plan(
    *,
    ffmpeg: MediaRuntimePort,
    input_path: str,
    prepared: PreparedRun,
    observers: RunObservers,
    resume_mode: str,
) -> tuple[ExecutionResult, float]:
    """Run the plan and return ``(result_dict, elapsed_seconds)``.

    Callers handle KeyboardInterrupt / ResumeConflictError / generic
    Exception so this function stays focused on the happy path.
    """
    start_time = time.time()
    if prepared.processing_steps:
        result = _run_streaming(
            ffmpeg=ffmpeg,
            input_path=input_path,
            prepared=prepared,
            observers=observers,
            resume_mode=resume_mode,
        )
    else:
        result = _run_format_conversion(
            ffmpeg=ffmpeg,
            input_path=input_path,
            prepared=prepared,
            observers=observers,
            resume_mode=resume_mode,
        )
    elapsed = round(time.time() - start_time, 2)
    return result, elapsed


def finalize_and_emit(
    *,
    observers: RunObservers,
    result: ExecutionResult,
    elapsed: float,
) -> None:
    """Finish the progress bar and emit a typed completed envelope."""
    observers.progress_reporter.finish()
    ndjson.emit(
        BackendEnvelopeType.COMPLETED,
        TaskCompletedPayload(
            output_path=result.output_path,
            processed_frames=result.processed_frames,
            time_seconds=elapsed,
        ),
    )
