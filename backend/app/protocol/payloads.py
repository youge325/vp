"""Typed NDJSON stream payloads emitted by the Python backend.

The Tauri host decodes these four payloads through Rust ``NdjsonEnvelope``.
Keeping the Python side typed catches schema drift before an invalid stdout
line crosses the process boundary.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, field_validator

from app.errors._codes import TaskErrorCode


def _to_camel(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class _PayloadBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    def to_wire(self) -> dict[str, Any]:
        """Return the camelCase JSON object consumed by the Rust host."""
        return self.model_dump(by_alias=True, mode="json", exclude_none=True)


class TaskProgressPayload(_PayloadBase):
    current: NonNegativeInt
    total: NonNegativeInt
    percent: float
    stage: str
    stage_index: NonNegativeInt
    stage_total: NonNegativeInt
    metrics: dict[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        payload = super().to_wire()
        if not self.metrics:
            payload.pop("metrics", None)
        return payload


class TaskCompletedPayload(_PayloadBase):
    output_path: str
    processed_frames: NonNegativeInt
    time_seconds: float


class TaskErrorPayload(_PayloadBase):
    code: TaskErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("details", mode="before")
    @classmethod
    def _default_details(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        return value


class ResumeStatusPayload(_PayloadBase):
    resumed: bool
    completed_chunks: NonNegativeInt
    completed_output_frames: NonNegativeInt
    start_source_frame: NonNegativeInt
    total_output_frames: NonNegativeInt
