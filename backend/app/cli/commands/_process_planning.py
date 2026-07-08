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

from app.cli.runtime_configs import RuntimeConfigs
from app.config import settings
from app.errors import TaskErrorCode, raise_error
from app.planning import (
    ProcessingStep,
    resolve_expected_output_frames,
    resolve_processing_steps,
    resolve_workflow_and_output_fps,
    verify_model_availability,
    verify_super_resolution_backend,
)
from app.processing.streaming.metrics import PipelineMetrics
from app.protocol.reporter import CliProgressReporter
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import get_output_path


@dataclass
class ProcessingPlan:
    """Everything ``cmd_process`` needs after planning is done."""

    output_path: str
    output_dir: str
    runtime_configs: RuntimeConfigs
    processing_steps: list[ProcessingStep]
    tensor_backend_name: str
    final_output_fps: float | None
    expected_output_frames: int
    progress_reporter: CliProgressReporter
    progress_callbacks: list[Callable[[int, int], None]]
    metrics: PipelineMetrics


def _make_stage_progress_callback(
    *,
    reporter: CliProgressReporter,
    stage_index: int,
    stage_total: int,
    stage_name: str,
) -> Callable[..., None]:
    """Build a progress callback that pins this stage's identity into the reporter.

    Phase C.1.3 — each step gets its own closure so the reporter knows
    ``stage_name`` / ``stage_index`` / ``stage_total`` before emitting the
    NDJSON progress frame. ``_total`` is ignored: ``CliProgressReporter``
    already knows the expected output frame count and uses that as the
    denominator for percent calculation.
    """

    def callback(current: int, total: int, **kwargs: Any) -> None:
        reporter.set_stage(stage_name, stage_index, stage_total, total_frames=total)
        reporter.update(
            current,
            total_frames=total,
            force=bool(kwargs.get("force") or False),
            heartbeat=bool(kwargs.get("heartbeat") or False),
        )

    return callback


def _resolve_output_paths(
    args: argparse.Namespace,
    input_path: str,
    configs: RuntimeConfigs,
) -> tuple[str, str]:
    """Pick the (output_dir, output_path) pair, materialising parents on disk."""
    # Phase 18 — Pydantic ``OutputConfig`` validator 保证 outputDir 必填非空,
    # 这里不再 ``or settings.OUTPUT_DIR`` 兜底;若 dict 来源绕过 Pydantic
    # (CLI defaults 路径),直接 KeyError → 立即 fail 暴露上游 bug。
    output_dir = configs.output.output_dir
    if not output_dir:
        raise_error(TaskErrorCode.INVALID_CONFIG, "outputDir is required.")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.RIFE_MODEL_DIR).mkdir(parents=True, exist_ok=True)

    container = configs.encode.container or "mp4"
    if args.output:
        output_path = args.output
        Path(output_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")
    return output_dir, output_path


def build_plan(
    args: argparse.Namespace,
    input_path: str,
    ffmpeg: FFmpegWrapper,
    configs: RuntimeConfigs,
) -> ProcessingPlan:
    """Compose the full ``ProcessingPlan`` for execution."""
    workflow_config = configs.workflow_json
    processing_steps = resolve_processing_steps(workflow_config)
    tensor_backend_name = configs.workflow.interpolation.tensor_backend or args.backend

    verify_super_resolution_backend(workflow_config, tensor_backend_name)
    verify_model_availability(workflow_config, processing_steps, tensor_backend_name)

    output_dir, output_path = _resolve_output_paths(args, input_path, configs)

    # Phase D.6.3 — multi 写回 + final_output_fps 推导收敛到 defaults helper,
    # 与 cmd_inspect_output 共享一份"不 mutate 原 dict"的语义。
    workflow_config, final_output_fps = resolve_workflow_and_output_fps(
        workflow_config,
        ffmpeg,
        input_path,
    )
    configs = configs.with_workflow_json(workflow_config)

    expected_output_frames = resolve_expected_output_frames(
        ffmpeg=ffmpeg,
        input_path=input_path,
        workflow_config=workflow_config,
        processing_steps=processing_steps,
        final_output_fps=final_output_fps,
    )
    # Phase D.2.3 — single PipelineMetrics instance shared between the
    # reporter (read-side: snapshot rides on each NDJSON progress frame)
    # and the workers (write-side: queue depth / processed frames).
    metrics = PipelineMetrics()
    progress_reporter = CliProgressReporter(expected_output_frames, metrics=metrics)

    # Phase C.1.3:per-stage 独立闭包,每次 update 前先 set_stage,
    # 让 NDJSON `progress.stageIndex/stageTotal` 真实反映当前阶段位置。
    # 原代码中所有 stage 共用同一份 lambda,导致前端永远只看到 stage_index=1。
    progress_callbacks: list[Callable[[int, int], None]] = [
        _make_stage_progress_callback(
            reporter=progress_reporter,
            stage_index=stage_index,
            stage_total=len(processing_steps),
            stage_name=step.stage_name or step.algorithm_type or f"stage_{stage_index}",
        )
        for stage_index, step in enumerate(processing_steps, start=1)
    ]

    return ProcessingPlan(
        output_path=output_path,
        output_dir=output_dir,
        runtime_configs=configs,
        processing_steps=processing_steps,
        tensor_backend_name=tensor_backend_name,
        final_output_fps=final_output_fps,
        expected_output_frames=expected_output_frames,
        progress_reporter=progress_reporter,
        progress_callbacks=progress_callbacks,
        metrics=metrics,
    )
