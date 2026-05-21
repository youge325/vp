"""``python -m app process`` handler — orchestration only.

Phase C.1.1 拆分:本文件保留为薄入口,串联 3 个子阶段:
1. ``_process_validation`` 校验输入并加载 4 个 config dict
2. ``_process_planning``  生成 ``ProcessingPlan``(stage 列表 / 输出路径 / fps / 进度回调)
3. ``_process_execution`` 跑 streaming pipeline 或 fast-path,emit ``ndjson.completed``

顶层 try/except 把 KeyboardInterrupt / ResumeConflictError / 其它 Exception
归一为 ``ProcessError``,后续由 ``__main__.py`` 转 NDJSON ``error`` 帧。
"""

from __future__ import annotations

import argparse

from app.cli.commands._process_execution import execute_plan, finalize_and_emit
from app.cli.commands._process_planning import build_plan
from app.cli.commands._process_validation import ensure_input_and_ffmpeg, load_configs
from app.cli.defaults import _resolve_primary_algorithm
from app.errors import ProcessError, ResumeConflictError, TaskErrorCode


def cmd_process(args: argparse.Namespace) -> None:
    input_path: str = args.input
    ffmpeg = ensure_input_and_ffmpeg(input_path)
    decode_config, encode_config, workflow_config, output_config = load_configs(args)

    plan = build_plan(
        args=args,
        input_path=input_path,
        ffmpeg=ffmpeg,
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
    )

    resume_mode = getattr(args, "resume_mode", "auto")
    try:
        result, elapsed = execute_plan(
            ffmpeg=ffmpeg,
            input_path=input_path,
            plan=plan,
            decode_config=decode_config,
            encode_config=encode_config,
            workflow_config=workflow_config,
            output_config=output_config,
            resume_mode=resume_mode,
        )
        finalize_and_emit(ffmpeg=ffmpeg, plan=plan, result=result, elapsed=elapsed)
    except KeyboardInterrupt:
        raise ProcessError(
            TaskErrorCode.CANCELLED,
            "Processing was cancelled by the user.",
            details={"input_path": input_path},
        )
    except ResumeConflictError as exc:
        # Phase A — ResumeConflictError 已继承 ProcessError 并预置 code+details;
        # 这里只需把 input_path 注入 details,保持对上层 NDJSON 的对外契约。
        exc.details.setdefault("input_path", input_path)
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details.update(
            {
                "input_path": input_path,
                "output_path": plan.output_path,
                "algorithm": _resolve_primary_algorithm(workflow_config),
                "processing_steps": [step["algorithm_type"] for step in plan.processing_steps],
            }
        )
        raise pe
