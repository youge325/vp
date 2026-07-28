"""Domain-facing access to generated configuration boundary models.

The field sets and wire aliases live only in ``app.generated.contracts``.
This module may add domain validation, but must not redeclare boundary fields.
"""

from __future__ import annotations

from pydantic import field_validator

from app.generated.contracts import (
    DecodeConfig,
    EncodeConfig,
    FilterStep,
    FilterStepKind,
    FpsMode,
    InterpolationConfig,
    PostprocessConfig,
    PreprocessConfig,
    ProcessOrder,
    RateControlConfig,
    RateControlMode,
    SuperResolutionConfig,
    TensorBackend,
    WorkflowConfig,
)
from app.generated.contracts import OutputConfig as _GeneratedOutputConfig


class OutputConfig(_GeneratedOutputConfig):
    """Generated output boundary plus the non-blank path domain invariant."""

    @field_validator("output_dir")
    @classmethod
    def _output_dir_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("output_dir must not be empty or whitespace-only")
        return value


__all__ = [
    "DecodeConfig",
    "EncodeConfig",
    "FilterStep",
    "FilterStepKind",
    "FpsMode",
    "InterpolationConfig",
    "OutputConfig",
    "PostprocessConfig",
    "PreprocessConfig",
    "ProcessOrder",
    "RateControlConfig",
    "RateControlMode",
    "SuperResolutionConfig",
    "TensorBackend",
    "WorkflowConfig",
]
