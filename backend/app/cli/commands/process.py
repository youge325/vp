"""``python -m app process`` handler — orchestration only.

本文件保留为薄入口,串联 3 个子阶段:
1. ``_process_validation`` 加载并校验类型化 runtime config
2. ``_process_planning`` 生成不可变 ``PreparedRun`` 与运行期 ``RunObservers``
3. ``_process_execution`` 跑 streaming pipeline 或 fast-path,emit ``ndjson.completed``

顶层 try/except 把 KeyboardInterrupt / ResumeConflictError / 其它 Exception
归一为 ``ProcessError``,后续由 ``__main__.py`` 转 NDJSON ``error`` 帧。
"""

from __future__ import annotations

import argparse

from app.cli.commands._process_execution import execute_plan, finalize_and_emit
from app.cli.commands._guards import ensure_input_and_ffmpeg
from app.cli.commands._process_planning import build_plan
from app.cli.commands._process_validation import load_runtime_configs
from app.errors import ProcessError, ResumeConflictError, TaskErrorCode
from app.planning import resolve_primary_algorithm


def cmd_process(args: argparse.Namespace) -> None:
    input_path: str = args.input
    ffmpeg = ensure_input_and_ffmpeg(input_path)
    configs = load_runtime_configs(args)

    prepared, observers = build_plan(
        args=args,
        input_path=input_path,
        ffmpeg=ffmpeg,
        configs=configs,
    )
    resume_mode = args.resume_mode
    try:
        result, elapsed = execute_plan(
            ffmpeg=ffmpeg,
            input_path=input_path,
            prepared=prepared,
            observers=observers,
            resume_mode=resume_mode,
        )
        finalize_and_emit(
            ffmpeg=ffmpeg,
            prepared=prepared,
            observers=observers,
            result=result,
            elapsed=elapsed,
        )
    except KeyboardInterrupt:
        raise ProcessError(
            TaskErrorCode.CANCELLED,
            "Processing was cancelled by the user.",
            details={"input_path": input_path},
        )
    except ResumeConflictError as exc:
        # ResumeConflictError 已继承 ProcessError 并预置 code+details。
        exc.details.setdefault("input_path", input_path)
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details.update(
            {
                "input_path": input_path,
                "output_path": prepared.output_path,
                "algorithm": resolve_primary_algorithm(prepared.runtime_configs.json_section("workflow")),
                "processing_steps": [step.algorithm_type for step in prepared.processing_steps],
            }
        )
        raise pe
