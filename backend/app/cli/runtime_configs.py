"""Typed runtime config bundle for process / inspect-output commands.

The Python CLI still receives and passes camelCase JSON dictionaries at the
wire boundaries. Internally, the orchestration layers can use the Pydantic
models here without losing the legacy dict shape used by FFmpeg wrappers,
resume signatures, and streaming tests.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any

from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig


def _copy_json_dict(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)


@dataclass(frozen=True, slots=True)
class RuntimeConfigs:
    """Validated configs plus their legacy camelCase dict snapshots."""

    decode: DecodeConfig
    encode: EncodeConfig
    workflow: WorkflowConfig
    output: OutputConfig
    decode_json: dict[str, Any]
    encode_json: dict[str, Any]
    workflow_json: dict[str, Any]
    output_json: dict[str, Any]

    def legacy_sections(self) -> dict[str, dict[str, Any]]:
        """Return the four wire sections as defensive copies."""
        return {
            "decode": _copy_json_dict(self.decode_json),
            "encode": _copy_json_dict(self.encode_json),
            "workflow": _copy_json_dict(self.workflow_json),
            "output": _copy_json_dict(self.output_json),
        }

    def legacy_tuple(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Return ``(decode, encode, workflow, output)`` for legacy callers."""
        sections = self.legacy_sections()
        return sections["decode"], sections["encode"], sections["workflow"], sections["output"]

    def with_workflow_json(self, workflow_json: dict[str, Any]) -> "RuntimeConfigs":
        """Return a bundle with workflow model and legacy snapshot kept in sync."""
        workflow = WorkflowConfig.model_validate(workflow_json)
        return replace(
            self,
            workflow=workflow,
            workflow_json=_copy_json_dict(workflow_json),
        )
