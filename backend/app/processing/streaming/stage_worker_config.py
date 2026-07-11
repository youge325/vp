"""JSON config model for one isolated stage-worker process."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from app.planning import ProcessingStep, normalize_processing_step


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
    tensor_backend_name: str
    output_frame_count: int | None = None

    @classmethod
    def from_json_file(cls, path: str | Path) -> "StageWorkerConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise ValueError("Stage worker config must be a JSON object.")

        def value(camel: str, snake: str) -> Any:
            return payload[camel] if camel in payload else payload[snake]

        return cls(
            stage=normalize_processing_step(value("stage", "stage")),
            stage_index=int(value("stageIndex", "stage_index")),
            stage_total=int(value("stageTotal", "stage_total")),
            stage_name=str(value("stageName", "stage_name")),
            input_width=int(value("inputWidth", "input_width")),
            input_height=int(value("inputHeight", "input_height")),
            output_width=int(value("outputWidth", "output_width")),
            output_height=int(value("outputHeight", "output_height")),
            input_frame_count=int(value("inputFrameCount", "input_frame_count")),
            tensor_backend_name=str(value("tensorBackendName", "tensor_backend_name")),
            output_frame_count=int(payload.get("outputFrameCount") or payload.get("output_frame_count") or 0) or None,
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
