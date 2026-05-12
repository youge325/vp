"""Stage 1 — input validation & config loading for ``cmd_process``.

只负责"把 args 翻译成已校验的运行时配置",**不做** stage planning / 模型路径
解析 / 流水线执行。这一层保证之后的 planning / execution 拿到的 dict 是
Pydantic 校验过、camelCase、已合并默认值的形状。

Phase C.1.1 将原 ``process.py`` 中的 297 行单文件拆为
validation / planning / execution / orchestrator 四段,本文件为第一段。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from app.cli.defaults import (
    _default_decode_config,
    _default_encode_config,
    _default_output_config,
    _default_workflow_config,
)
from app.errors import TaskErrorCode, emit_error
from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import validate_input_path


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
    """Parse + deep-merge + Pydantic-validate a ``--*-config-json`` arg."""
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


def ensure_input_and_ffmpeg(input_path: str) -> FFmpegWrapper:
    """Fail-fast guards before any config work happens.

    Returns the resolved ``FFmpegWrapper`` so callers don't have to construct
    it twice. Either guard failing emits a typed ``ProcessError``.
    """
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
    return ffmpeg


def load_configs(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Materialise the four config dicts from CLI JSON args.

    Returns ``(decode_config, encode_config, workflow_config, output_config)``
    — all camelCase, all Pydantic-validated. ``ValueError`` from any
    sub-call is caught and re-emitted as ``INVALID_CONFIG`` so the frontend
    sees a typed error rather than a stack trace.
    """
    try:
        decode_config = _load_json_arg(args.decode_config_json, _default_decode_config(), DecodeConfig)
        encode_config = _load_json_arg(args.encode_config_json, _default_encode_config(args), EncodeConfig)
        workflow_config = _load_json_arg(args.workflow_config_json, _default_workflow_config(args), WorkflowConfig)
        output_config = _load_json_arg(args.output_config_json, _default_output_config(args), OutputConfig)
    except ValueError as exc:
        emit_error(TaskErrorCode.INVALID_CONFIG, str(exc))
        raise  # unreachable; appeases the type-checker

    return decode_config, encode_config, workflow_config, output_config
