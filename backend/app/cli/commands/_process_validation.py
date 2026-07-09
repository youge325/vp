"""Stage 1 — input validation & config loading for ``cmd_process``.

只负责"把 args 翻译成已校验的运行时配置",**不做** stage planning / 模型路径
解析 / 流水线执行。这一层保证之后的 planning / execution 拿到的 dict 是
Pydantic 校验过、camelCase、已合并默认值的形状。

Phase C.1.1 将原 ``process.py`` 中的 297 行单文件拆为
validation / planning / execution / orchestrator 四段,本文件为第一段。

Phase D.3.1 — ``load_configs`` 现在支持两种 wire 格式:
- ``--config-stdin``:Tauri host 把 ``{decode, workflow, encode, output}``
  作为单个 JSON 对象写入 stdin。规避 Windows 32 KiB 命令行上限。
- ``--*-config-json``(传统):每段配置走独立命令行参数。手动 CLI 与测试
  仍走这条,保持兼容。
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
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import validate_input_path

ConfigModel = TypeVar("ConfigModel", DecodeConfig, EncodeConfig, WorkflowConfig, OutputConfig)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_config_section(
    raw_value: str | None,
    default: dict[str, Any],
    model_cls: type[ConfigModel],
) -> tuple[ConfigModel, dict[str, Any]]:
    """Parse + deep-merge + Pydantic-validate one config section.

    ``legacy`` intentionally mirrors the old CLI section dict shape:
    defaults without an override keep their original dict shape, while an
    explicit JSON payload round-trips through Pydantic and gains model
    defaults. Output config is the exception: even the default path must
    validate so missing outputDir fails loudly.
    """
    has_override = bool(raw_value)
    if has_override:
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        merged = _deep_merge(default, payload)
    else:
        merged = copy.deepcopy(default)

    try:
        validated = model_cls.model_validate(merged)
    except Exception as exc:
        raise ValueError(f"Config validation failed for {model_cls.__name__}: {exc}") from exc

    if isinstance(validated, OutputConfig) and not validated.output_dir:
        raise ValueError("Config validation failed for OutputConfig: outputDir is required.")

    legacy = validated.model_dump(by_alias=True) if has_override else merged
    return validated, legacy


def ensure_input_and_ffmpeg(input_path: str) -> FFmpegWrapper:
    """Fail-fast guards before any config work happens.

    Returns the resolved ``FFmpegWrapper`` so callers don't have to construct
    it twice. Either guard failing emits a typed ``ProcessError``.
    """
    if not validate_input_path(input_path):
        raise_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        raise_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )
    return ffmpeg


def _read_stdin_config_sections() -> dict[str, str | None]:
    """Read the four config sections from stdin as a single JSON object.

    Returns a ``{decode, workflow, encode, output}`` dict where each value
    is a JSON string (or ``None`` if the section is missing). Reusing the
    string form lets ``load_runtime_configs`` validate stdin and CLI paths
    through the same section loader, including the deep-merge + Pydantic round-trip.
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

    def _section(key: str) -> str | None:
        value = container.get(key)
        if value is None:
            return None
        return json.dumps(value)

    return {
        "decode": _section("decode"),
        "workflow": _section("workflow"),
        "encode": _section("encode"),
        "output": _section("output"),
    }


def _collect_config_sections(args: argparse.Namespace) -> dict[str, str | None]:
    """Choose between the stdin and CLI-flag wire formats.

    Returns the same ``{decode, workflow, encode, output}`` shape so that
    ``load_runtime_configs`` and ``cmd_inspect_output`` can stay format-agnostic.
    ``--config-stdin`` takes precedence; the four ``--*-config-json``
    flags are ignored when it's set (the parser still accepts them so
    older tooling doesn't break, but the documentation calls this out).
    """
    if getattr(args, "config_stdin", False):
        return _read_stdin_config_sections()
    return {
        "decode": args.decode_config_json,
        "workflow": args.workflow_config_json,
        "encode": args.encode_config_json,
        "output": args.output_config_json,
    }


def load_runtime_configs(args: argparse.Namespace) -> RuntimeConfigs:
    """Materialise typed runtime configs from CLI JSON args or stdin.

    The returned bundle carries Pydantic models for internal code and the
    legacy camelCase dict snapshots for existing wire/FFmpeg/signature
    boundaries. ``ValueError`` from any sub-call is caught and re-emitted
    as ``INVALID_CONFIG`` so the frontend sees a typed error rather than a
    stack trace.
    """
    sections = _collect_config_sections(args)
    try:
        decode, decode_json = _validate_config_section(sections["decode"], _default_decode_config(), DecodeConfig)
        encode, encode_json = _validate_config_section(
            sections["encode"],
            _default_encode_config(args),
            EncodeConfig,
        )
        workflow, workflow_json = _validate_config_section(
            sections["workflow"],
            _default_workflow_config(args),
            WorkflowConfig,
        )
        output, output_json = _validate_config_section(
            sections["output"],
            _default_output_config(args),
            OutputConfig,
        )
    except ValueError as exc:
        raise_error(TaskErrorCode.INVALID_CONFIG, str(exc))
        raise  # unreachable; appeases the type-checker

    return RuntimeConfigs(
        decode=decode,
        encode=encode,
        workflow=workflow,
        output=output,
        decode_json=decode_json,
        encode_json=encode_json,
        workflow_json=workflow_json,
        output_json=output_json,
    )
