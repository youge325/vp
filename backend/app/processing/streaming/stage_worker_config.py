"""JSON config model for one isolated stage-worker process."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, cast, get_args

from app.planning.processing_steps import AlgorithmType, ProcessingStep


def _parse_processing_step(payload: Any) -> ProcessingStep:
    if not isinstance(payload, Mapping):
        raise TypeError(f"Processing step must be a mapping, got {type(payload).__name__}.")

    algorithm_type = payload.get("algorithm_type")
    if not isinstance(algorithm_type, str) or algorithm_type not in get_args(AlgorithmType):
        raise ValueError(f"Unknown processing step algorithm_type: {algorithm_type!r}")

    algorithm_kwargs = payload.get("algorithm_kwargs", {})
    if algorithm_kwargs is None:
        algorithm_kwargs = {}
    if not isinstance(algorithm_kwargs, Mapping):
        raise TypeError("Processing step algorithm_kwargs must be a mapping.")

    stage_name = payload.get("stage_name")
    if not isinstance(stage_name, str) or not stage_name:
        raise ValueError("Processing step stage_name must be a non-empty string.")

    return ProcessingStep(
        algorithm_type=cast(AlgorithmType, algorithm_type),
        algorithm_kwargs=dict(algorithm_kwargs),
        stage_name=stage_name,
    )


@dataclass(frozen=True, slots=True)
class StageWorkerConfig:
    """JSON-serialisable configuration for one isolated algorithm stage."""

    stage: ProcessingStep
    stage_index: int
    stage_total: int
    stage_name: str
    input_width: int
    input_height: int
    output_width: int
    output_height: int
    input_frame_count: int
    tensor_backend_name: str | None
    output_frame_count: int | None = None

    def __post_init__(self) -> None:
        needs_backend = self.stage.algorithm_type in {"frame_interpolation", "super_resolution"}
        if needs_backend and not self.tensor_backend_name:
            raise ValueError(f"Stage '{self.stage_name}' requires a tensor backend.")
        if self.stage.algorithm_type == "frame_filter_chain" and self.tensor_backend_name is not None:
            raise ValueError(f"Filter stage '{self.stage_name}' must not consume a tensor backend.")

    @classmethod
    def from_json_file(cls, path: str | Path) -> "StageWorkerConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise ValueError("Stage worker config must be a JSON object.")

        backend_name = payload["tensorBackendName"]
        if backend_name is not None and (not isinstance(backend_name, str) or not backend_name):
            raise ValueError("tensorBackendName must be a non-empty string or null.")

        return cls(
            stage=_parse_processing_step(payload["stage"]),
            stage_index=int(payload["stageIndex"]),
            stage_total=int(payload["stageTotal"]),
            stage_name=str(payload["stageName"]),
            input_width=int(payload["inputWidth"]),
            input_height=int(payload["inputHeight"]),
            output_width=int(payload["outputWidth"]),
            output_height=int(payload["outputHeight"]),
            input_frame_count=int(payload["inputFrameCount"]),
            tensor_backend_name=backend_name,
            output_frame_count=(
                int(payload["outputFrameCount"]) if payload.get("outputFrameCount") is not None else None
            ),
        )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "stage": self.stage.to_jsonable(),
            "stageIndex": self.stage_index,
            "stageTotal": self.stage_total,
            "stageName": self.stage_name,
            "inputWidth": self.input_width,
            "inputHeight": self.input_height,
            "outputWidth": self.output_width,
            "outputHeight": self.output_height,
            "inputFrameCount": self.input_frame_count,
            "tensorBackendName": self.tensor_backend_name,
            "outputFrameCount": self.output_frame_count,
        }


__all__ = ["StageWorkerConfig"]
