"""Input validation and config loading for ``cmd_process``.

只负责"把 args 翻译成已校验的运行时配置",**不做** stage planning / 模型路径
解析 / 流水线执行。这一层保证之后的 planning / execution 拿到的 dict 是
Pydantic 校验过、camelCase、已合并默认值的形状。

``--config-stdin`` 接收 Tauri host 写入的中立
``{decode, workflow, encode, output}`` 对象；未设置时仅使用正式标量 CLI
参数构建默认配置。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any, TypeVar

from app.cli.defaults import (
    _default_decode_config,
    _default_encode_config,
    _default_output_config,
    _default_workflow_config,
)
from app.cli.runtime_configs import RuntimeConfigs
from app.errors import TaskErrorCode, raise_error
from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig

_ConfigModel = TypeVar("_ConfigModel", DecodeConfig, EncodeConfig, WorkflowConfig, OutputConfig)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_config_section(
    raw_value: dict[str, Any] | None,
    default: dict[str, Any],
    model_cls: type[_ConfigModel],
) -> _ConfigModel:
    """Deep-merge and validate one config section.

    RuntimeConfigs later projects default sections sparsely and explicit
    sections as complete camelCase dictionaries.
    """
    if raw_value is not None:
        merged = _deep_merge(default, raw_value)
    else:
        merged = copy.deepcopy(default)

    try:
        validated = model_cls.model_validate(merged)
    except Exception as exc:
        raise ValueError(f"Config validation failed for {model_cls.__name__}: {exc}") from exc

    if isinstance(validated, OutputConfig) and (validated.output_dir is None or not validated.output_dir.strip()):
        raise ValueError("Config validation failed for OutputConfig: outputDir is required.")

    return validated


def _read_stdin_config_sections() -> dict[str, dict[str, Any] | None]:
    """Read the four config sections from stdin as a single JSON object.

    Missing sections use scalar CLI defaults; present sections must themselves
    be objects and are validated after deep-merging those defaults.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            "Empty stdin payload while --config-stdin was set.",
        )
    try:
        container = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            f"Invalid stdin JSON: {exc}",
        )
    if not isinstance(container, dict):
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            "Stdin payload must be a JSON object with decode/workflow/encode/output keys.",
        )

    def _section(key: str) -> dict[str, Any] | None:
        value = container.get(key)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise_error(
                TaskErrorCode.INVALID_CONFIG,
                f"Stdin config section '{key}' must be a JSON object.",
            )
        return value

    return {
        "decode": _section("decode"),
        "workflow": _section("workflow"),
        "encode": _section("encode"),
        "output": _section("output"),
    }


def load_runtime_configs(args: argparse.Namespace) -> RuntimeConfigs:
    """Materialise typed runtime configs from scalar CLI args or stdin.

    The returned bundle carries Pydantic models for internal code and records
    which sections were explicit so wire projections preserve their shape.
    ``ValueError`` from any sub-call is caught and re-emitted
    as ``INVALID_CONFIG`` so the frontend sees a typed error rather than a
    stack trace.
    """
    sections: dict[str, dict[str, Any] | None]
    if args.config_stdin:
        sections = _read_stdin_config_sections()
    else:
        sections = {
            "decode": None,
            "workflow": None,
            "encode": None,
            "output": None,
        }
    try:
        decode = _validate_config_section(sections["decode"], _default_decode_config(), DecodeConfig)
        encode = _validate_config_section(
            sections["encode"],
            _default_encode_config(args),
            EncodeConfig,
        )
        workflow = _validate_config_section(
            sections["workflow"],
            _default_workflow_config(args),
            WorkflowConfig,
        )
        output = _validate_config_section(
            sections["output"],
            _default_output_config(args),
            OutputConfig,
        )
    except ValueError as exc:
        raise_error(TaskErrorCode.INVALID_CONFIG, str(exc))

    return RuntimeConfigs(
        decode=decode,
        encode=encode,
        workflow=workflow,
        output=output,
        _expanded_sections=frozenset(
            section for section in ("decode", "encode", "workflow", "output") if sections[section] is not None
        ),
    )
