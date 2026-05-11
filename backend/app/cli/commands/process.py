"""``python -m app process`` handler.

Drives the streaming pipeline end-to-end: validate inputs, merge defaults,
build the stage plan, run ``process_video_streaming`` (or the
format-conversion fast path), and emit ``ndjson.completed``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from app.cli.defaults import (
    _default_decode_config,
    _default_encode_config,
    _default_output_config,
    _default_workflow_config,
    _model_path,
    _processing_needs_interpolation,
    _resolve_expected_output_frames,
    _resolve_fps_and_multi,
    _resolve_primary_algorithm,
    _resolve_processing_steps,
)
from app.config import settings
from app.errors import ProcessError, ResumeConflictError, TaskErrorCode, emit_error
from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig
from app.processing.streaming import process_video_streaming
from app.protocol import ndjson
from app.protocol.reporter import CliProgressReporter
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import get_output_path, validate_input_path
from app.utils.onnx_models import resolve_onnx_model_path


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json_arg(
    raw_value: str | None,
    default: dict[str, Any],
    model_cls: type,
) -> dict[str, Any]:
    if not raw_value:
        return default
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object.")
    merged = _deep_merge(default, payload)
    try:
        validated = model_cls.model_validate(merged)
    except Exception as exc:
        raise ValueError(f"Config validation failed for {model_cls.__name__}: {exc}") from exc
    return validated.model_dump(by_alias=True)


def _get_onnx_model_name(config: dict[str, Any]) -> str | None:
    return config.get("onnxModel") or config.get("onnx_model")


def _validate_onnx_models_for_workflow(
    workflow_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    tensor_backend_name: str,
) -> None:
    if tensor_backend_name != "onnx":
        return

    for step in processing_steps:
        if step["algorithm_type"] == "frame_interpolation":
            model_name = _get_onnx_model_name(workflow_config["interpolation"])
            algorithm = workflow_config["interpolation"].get("algorithm", "rife")
            resolve_onnx_model_path("interpolation", algorithm, model_name, model_root=settings.RIFE_MODEL_DIR)
        elif step["algorithm_type"] == "super_resolution":
            model_name = _get_onnx_model_name(workflow_config["superResolution"])
            algorithm = workflow_config["superResolution"].get("algorithm", "placeholder")
            resolve_onnx_model_path("super_resolution", algorithm, model_name, model_root=settings.RIFE_MODEL_DIR)


def _resolve_processed_frame_count(ffmpeg: FFmpegWrapper, output_path: str, fallback: int) -> int:
    try:
        return ffmpeg.get_frame_count(output_path) or fallback
    except Exception:  # pragma: no cover - fallback for defensive CLI reporting
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


def cmd_process(args: argparse.Namespace) -> None:
    input_path = args.input
    if not validate_input_path(input_path):
        emit_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        emit_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )

    try:
        decode_config = _load_json_arg(args.decode_config_json, _default_decode_config(), DecodeConfig)
        encode_config = _load_json_arg(args.encode_config_json, _default_encode_config(args), EncodeConfig)
        workflow_config = _load_json_arg(args.workflow_config_json, _default_workflow_config(args), WorkflowConfig)
        output_config = _load_json_arg(args.output_config_json, _default_output_config(args), OutputConfig)
    except ValueError as exc:
        emit_error(TaskErrorCode.INVALID_CONFIG, str(exc))

    processing_steps = _resolve_processing_steps(workflow_config)
    tensor_backend_name = workflow_config["interpolation"].get("tensorBackend", args.backend)
    if _processing_needs_interpolation(processing_steps):
        if tensor_backend_name == "onnx":
            try:
                _validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name)
            except FileNotFoundError as exc:
                emit_error(
                    TaskErrorCode.MISSING_MODEL,
                    str(exc),
                    details={
                        "tensor_backend": tensor_backend_name,
                        "model_root": settings.RIFE_MODEL_DIR,
                    },
                )
        else:
            model_path = _model_path(workflow_config["interpolation"]["model"])
            if not model_path.is_file() or model_path.stat().st_size == 0:
                emit_error(
                    TaskErrorCode.MISSING_MODEL,
                    f"Default interpolation model is missing: {model_path}",
                    details={
                        "model_path": str(model_path),
                        "model_version": workflow_config["interpolation"]["model"],
                    },
                )
    elif tensor_backend_name == "onnx":
        try:
            _validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name)
        except FileNotFoundError as exc:
            emit_error(
                TaskErrorCode.MISSING_MODEL,
                str(exc),
                details={
                    "tensor_backend": tensor_backend_name,
                    "model_root": settings.RIFE_MODEL_DIR,
                },
            )

    output_dir = output_config.get("outputDir") or settings.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.RIFE_MODEL_DIR).mkdir(parents=True, exist_ok=True)

    container = str(encode_config.get("container") or "mp4")
    if args.output:
        output_path = args.output
        Path(output_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")

    multi, encode_fps, _interpolated_fps, need_resample = _resolve_fps_and_multi(workflow_config, ffmpeg, input_path)
    workflow_config["interpolation"]["multi"] = multi
    final_output_fps = encode_fps if need_resample else None
    expected_output_frames = _resolve_expected_output_frames(
        ffmpeg=ffmpeg,
        input_path=input_path,
        workflow_config=workflow_config,
        processing_steps=processing_steps,
        final_output_fps=final_output_fps,
    )
    progress_reporter = CliProgressReporter(expected_output_frames)

    # 为每个处理步骤生成进度回调，把源帧索引透传给编码进度条。
    # 百分比会与最终输出帧数不完全对齐，但至少能让前端看到进度在动。
    progress_callbacks = [
        lambda current, total, reporter=progress_reporter: reporter.update(current) for _ in processing_steps
    ]
    start_time = time.time()
    try:
        if processing_steps:
            result = process_video_streaming(
                ffmpeg=ffmpeg,
                input_path=input_path,
                output_path=output_path,
                decode_config=decode_config,
                encode_config=encode_config,
                workflow_config=workflow_config,
                output_config=output_config,
                processing_steps=processing_steps,
                tensor_backend_name=tensor_backend_name,
                progress_callbacks=progress_callbacks,
                output_fps=final_output_fps,
                encode_progress_callback=progress_reporter.update,
                resume_mode=getattr(args, "resume_mode", "auto"),
            )
        else:
            _enforce_format_conversion_resume_mode(
                output_path=output_path,
                resume_mode=getattr(args, "resume_mode", "auto"),
            )
            ffmpeg.transcode_video(
                input_path=input_path,
                output_path=output_path,
                decode_config=decode_config,
                encode_config=encode_config,
                progress_callback=lambda progress: progress_reporter.update(
                    int(progress.get("frame") or 0),
                    progress.get("fps"),
                    progress.get("speed"),
                    progress.get("out_time_seconds"),
                    str(progress.get("progress") or ""),
                ),
            )
            result = {
                "output_path": output_path,
                "processed_frames": _resolve_processed_frame_count(ffmpeg, output_path, expected_output_frames),
                "audio_merged": bool(encode_config.get("keepAudio", True)),
            }

        elapsed = round(time.time() - start_time, 2)
        processed_frames = _resolve_processed_frame_count(
            ffmpeg,
            str(result.get("output_path", output_path)),
            int(result.get("processed_frames", expected_output_frames) or expected_output_frames),
        )
        progress_reporter.finish(processed_frames)
        ndjson.completed(
            output_path=result.get("output_path", output_path),
            processed_frames=processed_frames,
            time_seconds=elapsed,
        )
    except KeyboardInterrupt:
        raise ProcessError(
            TaskErrorCode.CANCELLED,
            "Processing was cancelled by the user.",
            details={"input_path": input_path},
        )
    except ResumeConflictError as exc:
        raise ProcessError(
            TaskErrorCode.RESUME_CONFLICT,
            "An existing output was detected; please choose how to proceed.",
            details={
                "input_path": input_path,
                **exc.to_details(),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details.update(
            {
                "input_path": input_path,
                "output_path": output_path,
                "algorithm": _resolve_primary_algorithm(workflow_config),
                "processing_steps": [step["algorithm_type"] for step in processing_steps],
            }
        )
        raise pe
