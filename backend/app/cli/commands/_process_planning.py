"""Stage 2 — pipeline planning & path resolution for ``cmd_process``.

输入是 validation 阶段产出的 4 个 config dict,输出是一个 ``ProcessingPlan``
数据类,后续 execution 阶段直接消费它,无需再回头看 args / defaults。
ONNX 模型可用性、模型文件存在性、resume 输出路径、FPS / multi 计算、进度
回调装配都在这一层完成。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.cli.defaults import (
    _model_path,
    _processing_needs_interpolation,
    _resolve_expected_output_frames,
    _resolve_fps_and_multi,
    _resolve_processing_steps,
)
from app.config import settings
from app.errors import TaskErrorCode, emit_error
from app.protocol.reporter import CliProgressReporter
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import get_output_path
from app.utils.onnx_models import resolve_onnx_model_path


@dataclass
class ProcessingPlan:
    """Everything ``cmd_process`` needs after planning is done."""

    output_path: str
    output_dir: str
    processing_steps: list[dict[str, Any]]
    tensor_backend_name: str
    final_output_fps: float | None
    expected_output_frames: int
    progress_reporter: CliProgressReporter
    progress_callbacks: list[Callable[[int, int], None]]


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


def _make_stage_progress_callback(
    *,
    reporter: CliProgressReporter,
    stage_index: int,
    stage_total: int,
    stage_name: str,
) -> Callable[[int, int], None]:
    """Build a progress callback that pins this stage's identity into the reporter.

    Phase C.1.3 — each step gets its own closure so the reporter knows
    ``stage_name`` / ``stage_index`` / ``stage_total`` before emitting the
    NDJSON progress frame. ``_total`` is ignored: ``CliProgressReporter``
    already knows the expected output frame count and uses that as the
    denominator for percent calculation.
    """

    def callback(current: int, _total: int) -> None:
        reporter.set_stage(stage_name, stage_index, stage_total)
        reporter.update(current)

    return callback


def _verify_model_availability(
    workflow_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    tensor_backend_name: str,
) -> None:
    """Per-backend model existence guard.

    PyTorch / Paddle backends need the bundled RIFE weight file when
    interpolation is on; ONNX backend resolves model paths through
    ``resolve_onnx_model_path``. Both paths emit ``MISSING_MODEL`` on
    failure.
    """
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


def _resolve_output_paths(
    args: argparse.Namespace,
    input_path: str,
    output_config: dict[str, Any],
    encode_config: dict[str, Any],
) -> tuple[str, str]:
    """Pick the (output_dir, output_path) pair, materialising parents on disk."""
    output_dir = output_config.get("outputDir") or settings.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.RIFE_MODEL_DIR).mkdir(parents=True, exist_ok=True)

    container = str(encode_config.get("container") or "mp4")
    if args.output:
        output_path = args.output
        Path(output_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")
    return output_dir, output_path


def _verify_super_resolution_backend(
    workflow_config: dict[str, Any],
    tensor_backend_name: str,
) -> None:
    """Reject SR + non-ONNX combinations before the pipeline silently no-ops.

    Phase D.1.1 — ``SuperResolutionAlgorithm.process_frame`` only implements
    the ONNX path; pytorch / paddle backends return frames unchanged. Catching
    the invalid combo here surfaces ``INVALID_CONFIG`` to the frontend
    instead of letting the task complete with un-upscaled output.
    """
    if not workflow_config.get("superResolution", {}).get("enabled"):
        return
    if tensor_backend_name == "onnx":
        return
    emit_error(
        TaskErrorCode.INVALID_CONFIG,
        (
            "Super-resolution requires the ONNX tensor backend; "
            f"got '{tensor_backend_name}'. Switch the tensor backend to onnx "
            "or disable super-resolution."
        ),
        details={
            "tensor_backend": tensor_backend_name,
            "super_resolution_enabled": True,
        },
    )


def build_plan(
    args: argparse.Namespace,
    input_path: str,
    ffmpeg: FFmpegWrapper,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
) -> ProcessingPlan:
    """Compose the full ``ProcessingPlan`` for execution."""
    processing_steps = _resolve_processing_steps(workflow_config)
    tensor_backend_name = workflow_config["interpolation"].get("tensorBackend", args.backend)

    _verify_super_resolution_backend(workflow_config, tensor_backend_name)
    _verify_model_availability(workflow_config, processing_steps, tensor_backend_name)

    output_dir, output_path = _resolve_output_paths(args, input_path, output_config, encode_config)

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

    # Phase C.1.3:per-stage 独立闭包,每次 update 前先 set_stage,
    # 让 NDJSON `progress.stageIndex/stageTotal` 真实反映当前阶段位置。
    # 原代码中所有 stage 共用同一份 lambda,导致前端永远只看到 stage_index=1。
    progress_callbacks: list[Callable[[int, int], None]] = [
        _make_stage_progress_callback(
            reporter=progress_reporter,
            stage_index=stage_index,
            stage_total=len(processing_steps),
            stage_name=step.get("stage_name") or step.get("algorithm_type") or f"stage_{stage_index}",
        )
        for stage_index, step in enumerate(processing_steps, start=1)
    ]

    return ProcessingPlan(
        output_path=output_path,
        output_dir=output_dir,
        processing_steps=processing_steps,
        tensor_backend_name=tensor_backend_name,
        final_output_fps=final_output_fps,
        expected_output_frames=expected_output_frames,
        progress_reporter=progress_reporter,
        progress_callbacks=progress_callbacks,
    )
