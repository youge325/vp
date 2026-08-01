"""Generated runtime-bundle validation for ``cmd_process``."""

from __future__ import annotations

import argparse
import sys

from pydantic import ValidationError

from app.cli.defaults import (
    _default_decode_config,
    _default_encode_config,
    _default_output_config,
    _default_workflow_config,
)
from app.errors.codes import TaskErrorCode
from app.errors.process import raise_error
from app.generated.contracts import RuntimeConfigBundle


def _validate_output_directory(bundle: RuntimeConfigBundle) -> RuntimeConfigBundle:
    output_dir = bundle.output.output_dir
    if output_dir is None or not output_dir.strip():
        raise_error(TaskErrorCode.INVALID_CONFIG, "Config validation failed: outputDir is required.")
    return bundle


def _load_stdin_bundle() -> RuntimeConfigBundle:
    raw = sys.stdin.read()
    if not raw.strip():
        raise_error(
            TaskErrorCode.INVALID_CONFIG,
            "Empty stdin payload while --config-stdin was set.",
        )
    try:
        return RuntimeConfigBundle.model_validate_json(raw, by_alias=True, by_name=False)
    except ValidationError as exc:
        raise_error(TaskErrorCode.INVALID_CONFIG, f"Invalid runtime config bundle: {exc}")


def _build_default_bundle(args: argparse.Namespace) -> RuntimeConfigBundle:
    try:
        return RuntimeConfigBundle.model_validate(
            {
                "decode": _default_decode_config(),
                "workflow": _default_workflow_config(args),
                "encode": _default_encode_config(args),
                "output": _default_output_config(args),
            }
        )
    except ValidationError as exc:
        raise_error(TaskErrorCode.INVALID_CONFIG, f"Invalid default runtime config bundle: {exc}")


def load_runtime_configs(args: argparse.Namespace) -> RuntimeConfigBundle:
    """Load the strict generated bundle from stdin or scalar CLI defaults."""
    bundle = _load_stdin_bundle() if args.config_stdin else _build_default_bundle(args)
    return _validate_output_directory(bundle)


__all__ = ["load_runtime_configs"]
