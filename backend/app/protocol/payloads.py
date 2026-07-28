"""Wire adapters over generated NDJSON payload models.

Schema-owned fields, aliases, enum domains, and strict-extra behavior come
from ``app.generated.contracts``. The adapters only provide the emitter's
camelCase projection and its documented empty-value policy.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from app.generated.contracts import (
    BackendTaskErrorPayload as _GeneratedTaskErrorPayload,
)
from app.generated.contracts import (
    ResumeStatusPayload as _GeneratedResumeStatusPayload,
)
from app.generated.contracts import (
    TaskCompletedPayload as _GeneratedTaskCompletedPayload,
)
from app.generated.contracts import (
    TaskProgressPayload as _GeneratedTaskProgressPayload,
)


class _WirePayload:
    def to_wire(self: BaseModel) -> dict[str, Any]:
        """Return the camelCase object consumed by the Rust host."""
        return self.model_dump(by_alias=True, mode="json", exclude_none=True)


class TaskProgressPayload(_WirePayload, _GeneratedTaskProgressPayload):
    def to_wire(self) -> dict[str, Any]:
        payload = super().to_wire()
        if not self.metrics:
            payload.pop("metrics", None)
        return payload


class TaskCompletedPayload(_WirePayload, _GeneratedTaskCompletedPayload):
    pass


class TaskErrorPayload(_WirePayload, _GeneratedTaskErrorPayload):
    @field_validator("details", mode="before")
    @classmethod
    def _default_details(cls, value: Any) -> dict[str, Any]:
        return {} if value is None else value

    def to_wire(self) -> dict[str, Any]:
        payload = super().to_wire()
        payload["details"] = self.details or {}
        return payload


class ResumeStatusPayload(_WirePayload, _GeneratedResumeStatusPayload):
    pass


__all__ = [
    "ResumeStatusPayload",
    "TaskCompletedPayload",
    "TaskErrorPayload",
    "TaskProgressPayload",
]
