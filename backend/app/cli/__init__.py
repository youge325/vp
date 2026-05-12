"""VP Workbench CLI entry-point package.

Re-exports the minimal public surface for ``python -m app`` and
backward-compatible test imports.
"""

from __future__ import annotations

from app.cli.commands.check import cmd_check
from app.cli.commands.info import cmd_info
from app.cli.commands.inspect_output import cmd_inspect_output
from app.cli.commands.process import cmd_process

# Phase C.1.1 — process.py 拆分后,以下内部 helper 由子模块持有,
# 这里继续 re-export 以保证既有测试 import 路径不破坏。
from app.cli.commands._process_execution import (
    _enforce_format_conversion_resume_mode,
    _resolve_processed_frame_count,
)
from app.cli.commands._process_planning import (
    _get_onnx_model_name,
    _validate_onnx_models_for_workflow,
)
from app.cli.commands._process_validation import _deep_merge, _load_json_arg
from app.cli.defaults import (
    PROCESS_LABEL_MAP,
    PROCESS_ORDER_MAP,
    _build_algorithm_kwargs,
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
from app.cli.main import main
from app.cli.parser import _add_shared_planning_args, build_parser

__all__ = [
    "main",
    "build_parser",
    "cmd_check",
    "cmd_info",
    "cmd_process",
    "cmd_inspect_output",
    "PROCESS_LABEL_MAP",
    "PROCESS_ORDER_MAP",
    "_add_shared_planning_args",
    "_build_algorithm_kwargs",
    "_default_decode_config",
    "_default_encode_config",
    "_default_output_config",
    "_default_workflow_config",
    "_deep_merge",
    "_enforce_format_conversion_resume_mode",
    "_get_onnx_model_name",
    "_load_json_arg",
    "_model_path",
    "_processing_needs_interpolation",
    "_resolve_expected_output_frames",
    "_resolve_fps_and_multi",
    "_resolve_primary_algorithm",
    "_resolve_processed_frame_count",
    "_resolve_processing_steps",
    "_validate_onnx_models_for_workflow",
]
