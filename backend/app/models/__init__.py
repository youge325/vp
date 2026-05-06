"""Pydantic models mirroring the Rust IPC schema (frontend/src-tauri/src/models.rs).

These models validate incoming JSON from the Tauri layer and guarantee that
field names, types and defaults stay in sync with the Rust source of truth.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class _CamelBase(BaseModel):
    """Base with camelCase alias support so Tauri JSON payloads are accepted."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class DecodeConfig(_CamelBase):
    mode: str
    hwaccel: str | None = None
    hwaccel_device: str | None = None
    decoder: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class InterpolationConfig(_CamelBase):
    enabled: bool
    target_fps: float
    multi: int
    model: str
    onnx_model: str | None = None
    scale: float
    fp16: bool
    tensor_backend: str
    engine: str = "cuda"


class SuperResolutionConfig(_CamelBase):
    enabled: bool
    scale_factor: float
    algorithm: str
    onnx_model: str | None = None


class AnimeConfig(_CamelBase):
    enabled: bool
    profile: str
    denoise: int
    edge_boost: int


class FilterStep(_CamelBase):
    kind: str
    enabled: bool
    params: dict[str, Any] = Field(default_factory=dict)


class PreprocessConfig(_CamelBase):
    enabled: bool
    filters: list[FilterStep] = Field(default_factory=list)


class PostprocessConfig(_CamelBase):
    enabled: bool
    filters: list[FilterStep] = Field(default_factory=list)


class WorkflowConfig(_CamelBase):
    fps_mode: str
    process_order: str
    interpolation: InterpolationConfig
    super_resolution: SuperResolutionConfig
    anime: AnimeConfig
    preprocess: PreprocessConfig = Field(default_factory=lambda: PreprocessConfig(enabled=False, filters=[]))
    postprocess: PostprocessConfig = Field(default_factory=lambda: PostprocessConfig(enabled=False, filters=[]))


class RateControlConfig(_CamelBase):
    mode: str
    value: Any


class EncodeConfig(_CamelBase):
    codec: str
    family: str
    container: str
    keep_audio: bool
    rate_control: RateControlConfig
    options: dict[str, Any] = Field(default_factory=dict)


class OutputConfig(_CamelBase):
    output_dir: str
    open_on_complete: bool
    segment_frames: int
