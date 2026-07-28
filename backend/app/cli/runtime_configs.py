"""Typed runtime config bundle for process / inspect-output commands.

The Python CLI still receives and passes camelCase JSON dictionaries at the
wire boundaries. Internally, the orchestration layers can use the Pydantic
models here while projecting the canonical camelCase boundary shape used by
FFmpeg adapters, resume signatures, and streaming workers.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig


def _copy_json_dict(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)


_ConfigSection = Literal["decode", "encode", "workflow", "output"]


@dataclass(frozen=True, slots=True)
class RuntimeConfigs:
    """Validated config models with on-demand camelCase wire projections."""

    decode: DecodeConfig
    encode: EncodeConfig
    workflow: WorkflowConfig
    output: OutputConfig
    _expanded_sections: frozenset[_ConfigSection] = field(default_factory=frozenset, repr=False)

    def json_section(self, section: _ConfigSection) -> dict[str, Any]:
        """Project one model to its canonical camelCase boundary shape."""
        model = getattr(self, section)
        value = model.model_dump(
            by_alias=True,
            mode="json",
            exclude_unset=section not in self._expanded_sections,
        )
        return _copy_json_dict(value)

    def json_sections(self) -> dict[_ConfigSection, dict[str, Any]]:
        """Project all config models as independent defensive copies."""
        return {section: self.json_section(section) for section in ("decode", "encode", "workflow", "output")}

    def with_workflow(self, workflow: WorkflowConfig) -> "RuntimeConfigs":
        """Return a bundle with an updated validated workflow model."""
        return replace(self, workflow=workflow)
