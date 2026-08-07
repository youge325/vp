"""Small projections around the generated runtime-config boundary model."""

from __future__ import annotations

from typing import Any, Literal

from app.generated.contracts import RuntimeConfigBundle, WorkflowConfig

_ConfigSection = Literal["decode", "encode", "workflow", "output"]


def runtime_config_section(bundle: RuntimeConfigBundle, section: _ConfigSection) -> dict[str, Any]:
    return getattr(bundle, section).model_dump(by_alias=True, mode="json")


def runtime_config_sections(bundle: RuntimeConfigBundle) -> dict[str, dict[str, Any]]:
    return bundle.model_dump(by_alias=True, mode="json")


def with_workflow(bundle: RuntimeConfigBundle, workflow: WorkflowConfig) -> RuntimeConfigBundle:
    return bundle.model_copy(update={"workflow": workflow})
