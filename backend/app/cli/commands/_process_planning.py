"""Pipeline planning and path resolution for ``cmd_process``.

输入是 validation 阶段产出的 4 个 config dict，输出不可变的运行计划与观察者。
执行所需静态事实和带状态的进度/指标对象分开保存。
ONNX 模型可用性、模型文件存在性、resume 输出路径、FPS / multi 计算、进度
回调装配都在这一层完成。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.cli.commands._pipeline_preparation import PreparedRun, prepare_pipeline_preflight
from app.cli.runtime_configs import RuntimeConfigs
from app.config import settings
from app.errors import TaskErrorCode, raise_error
from app.ports.media import MediaProbePort
from app.planning import validate_workflow_requirements
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_progress import StageProgressCallback
from app.protocol.reporter import CliProgressReporter
from app.utils.file_utils import prepare_default_output_path


@dataclass(frozen=True, slots=True)
class RunObservers:
    """Mutable runtime collaborators kept outside the static run plan."""

    progress_reporter: CliProgressReporter
    progress_callbacks: tuple[StageProgressCallback, ...]
    metrics: PipelineMetrics


def _make_stage_progress_callback(
    *,
    reporter: CliProgressReporter,
    stage_index: int,
    stage_total: int,
    stage_name: str,
) -> StageProgressCallback:
    """Build a progress callback that pins this stage's identity into the reporter.

    Each step gets its own closure so the reporter knows
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
) -> str:
    """Pick the output path and materialise its parent directory."""
    # Pydantic ``OutputConfig`` validator 保证 outputDir 必填非空,
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
        output_path = prepare_default_output_path(input_path, output_dir, container)
    return output_path


def build_plan(
    args: argparse.Namespace,
    input_path: str,
    ffmpeg: MediaProbePort,
    configs: RuntimeConfigs,
) -> tuple[PreparedRun, RunObservers]:
    """Compose immutable run facts and their runtime observers."""
    output_path = _resolve_output_paths(args, input_path, configs)
    pipeline = prepare_pipeline_preflight(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        configs=configs,
    )
    processing_steps = pipeline.processing_steps
    validate_workflow_requirements(processing_steps)

    expected_output_frames = pipeline.preflight.stage_plan.total_encoded_frames
    metrics = PipelineMetrics()
    progress_reporter = CliProgressReporter(expected_output_frames, metrics=metrics)

    # 每个 stage 使用独立闭包，让 NDJSON 反映当前阶段位置。
    progress_callbacks = tuple(
        _make_stage_progress_callback(
            reporter=progress_reporter,
            stage_index=stage_index,
            stage_total=len(processing_steps),
            stage_name=step.stage_name or step.algorithm_type or f"stage_{stage_index}",
        )
        for stage_index, step in enumerate(processing_steps, start=1)
    )

    observers = RunObservers(
        progress_reporter=progress_reporter,
        progress_callbacks=progress_callbacks,
        metrics=metrics,
    )
    return pipeline, observers
