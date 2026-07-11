"""Stage 3 — pipeline execution & terminal NDJSON for ``cmd_process``.

收 ``ProcessingPlan`` + 4 个 config dict 后,选择 streaming pipeline 或
fast-path FFmpeg transcode 跑流水线,然后把结果格式化成 ``ndjson.completed``。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.cli.runtime_configs import RuntimeConfigs
from app.errors import ResumeConflictError
from app.processing.streaming import process_video_streaming
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper

from app.cli.commands._process_planning import ProcessingPlan


def _resolve_processed_frame_count(ffmpeg: FFmpegWrapper, output_path: str, fallback: int) -> int:
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
    if not target.exists():
        return
    if resume_mode in {"force-fresh", "force-resume"}:
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
    ffmpeg: FFmpegWrapper,
    input_path: str,
    plan: ProcessingPlan,
    configs: RuntimeConfigs,
    resume_mode: str,
) -> dict[str, Any]:
    sections = configs.legacy_sections()
    return process_video_streaming(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=plan.output_path,
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=sections["workflow"],
        output_config=sections["output"],
        processing_steps=plan.processing_steps,
        tensor_backend_name=plan.tensor_backend_name,
        progress_callbacks=plan.progress_callbacks,
        output_fps=plan.final_output_fps,
        encode_progress_callback=plan.progress_reporter.update,
        resume_mode=resume_mode,
        metrics=plan.metrics,
    )


def _run_format_conversion(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    plan: ProcessingPlan,
    configs: RuntimeConfigs,
    resume_mode: str,
) -> dict[str, Any]:
    sections = configs.legacy_sections()
    decode_config = sections["decode"]
    encode_config = sections["encode"]
    _enforce_format_conversion_resume_mode(output_path=plan.output_path, resume_mode=resume_mode)
    ffmpeg.transcode_video(
        input_path=input_path,
        output_path=plan.output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        progress_callback=lambda progress: plan.progress_reporter.update(
            int(progress.get("frame") or 0),
            progress.get("fps"),
            progress.get("speed"),
            progress.get("out_time_seconds"),
            str(progress.get("progress") or ""),
        ),
    )
    return {
        "output_path": plan.output_path,
        "processed_frames": _resolve_processed_frame_count(ffmpeg, plan.output_path, plan.expected_output_frames),
        "audio_merged": configs.encode.keep_audio,
    }


def execute_plan(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    plan: ProcessingPlan,
    configs: RuntimeConfigs,
    resume_mode: str,
) -> tuple[dict[str, Any], float]:
    """Run the plan and return ``(result_dict, elapsed_seconds)``.

    Callers handle KeyboardInterrupt / ResumeConflictError / generic
    Exception so this function stays focused on the happy path.
    """
    start_time = time.time()
    if plan.processing_steps:
        result = _run_streaming(
            ffmpeg=ffmpeg,
            input_path=input_path,
            plan=plan,
            configs=configs,
            resume_mode=resume_mode,
        )
    else:
        result = _run_format_conversion(
            ffmpeg=ffmpeg,
            input_path=input_path,
            plan=plan,
            configs=configs,
            resume_mode=resume_mode,
        )
    elapsed = round(time.time() - start_time, 2)
    return result, elapsed


def finalize_and_emit(
    *,
    ffmpeg: FFmpegWrapper,
    plan: ProcessingPlan,
    result: dict[str, Any],
    elapsed: float,
) -> None:
    """Finish the progress bar and emit ``ndjson.completed``."""
    processed_frames = _resolve_processed_frame_count(
        ffmpeg,
        str(result.get("output_path", plan.output_path)),
        int(result.get("processed_frames", plan.expected_output_frames) or plan.expected_output_frames),
    )
    plan.progress_reporter.finish()
    ndjson.completed(
        output_path=result.get("output_path", plan.output_path),
        processed_frames=processed_frames,
        time_seconds=elapsed,
    )
