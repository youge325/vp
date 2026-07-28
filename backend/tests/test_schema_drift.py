"""Generated-boundary ownership and strict decoding regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.errors import TaskErrorCode
from app.generated import contracts as generated
from app.models import DecodeConfig, OutputConfig, WorkflowConfig
from app.protocol.payloads import TaskErrorPayload, TaskProgressPayload

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts"


def _workflow() -> dict[str, object]:
    return {
        "fpsMode": "multi",
        "processOrder": "super_resolution_then_interpolation",
        "interpolation": {
            "enabled": False,
            "targetFps": 60.0,
            "multi": 2,
            "algorithm": "rife",
            "model": "4.25",
            "onnxModel": None,
            "scale": 1.0,
            "fp16": False,
            "tensorBackend": "pytorch",
            "engine": "cuda",
        },
        "superResolution": {
            "enabled": False,
            "scaleFactor": 2.0,
            "algorithm": "onnx",
            "onnxModel": None,
            "tensorBackend": "onnx",
            "engine": "cuda",
            "numFrames": 10,
        },
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }


def test_config_models_are_generated_or_thin_domain_subclasses() -> None:
    assert DecodeConfig is generated.DecodeConfig
    assert WorkflowConfig is generated.WorkflowConfig
    assert issubclass(OutputConfig, generated.OutputConfig)
    assert OutputConfig.model_fields.keys() == generated.OutputConfig.model_fields.keys()


def test_ndjson_adapters_reuse_generated_field_sets() -> None:
    assert issubclass(TaskProgressPayload, generated.TaskProgressPayload)
    assert TaskProgressPayload.model_fields.keys() == generated.TaskProgressPayload.model_fields.keys()
    assert issubclass(TaskErrorPayload, generated.BackendTaskErrorPayload)
    assert TaskErrorPayload.model_fields.keys() == generated.BackendTaskErrorPayload.model_fields.keys()


def test_generated_config_rejects_unknown_fields() -> None:
    value = _workflow()
    value["unexpected"] = True
    with pytest.raises(ValidationError, match="unexpected"):
        WorkflowConfig.model_validate(value)


def test_generated_task_request_rejects_unknown_fields() -> None:
    value = {
        "inputPath": "D:/input.mp4",
        "decodeConfig": {
            "mode": "software",
            "hwaccel": None,
            "hwaccelDevice": None,
            "decoder": None,
            "options": {},
        },
        "workflowConfig": _workflow(),
        "encodeConfig": {
            "codec": "libx264",
            "family": "software",
            "container": "mp4",
            "keepAudio": True,
            "rateControl": {"mode": "crf", "value": 18},
            "options": {},
        },
        "outputConfig": {
            "outputDir": "D:/out",
            "openOnComplete": False,
            "segmentFrames": 120,
        },
        "resumeMode": "auto",
        "unexpected": True,
    }
    with pytest.raises(ValidationError, match="unexpected"):
        generated.TaskRequest.model_validate(value)


def test_generated_ndjson_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="unexpected"):
        TaskProgressPayload.model_validate(
            {
                "current": 1,
                "total": 2,
                "percent": 50.0,
                "stage": "Encoding",
                "stageIndex": 1,
                "stageTotal": 1,
                "unexpected": 0,
            }
        )


def test_generated_numeric_unions_preserve_integer_identity() -> None:
    rate_control = generated.RateControlConfig.model_validate({"mode": "crf", "value": 18})
    option = generated.CapabilityChoice.model_validate({"label": "Tile", "value": 320})
    assert rate_control.model_dump(mode="json")["value"] == 18
    assert isinstance(rate_control.model_dump(mode="json")["value"], int)
    assert option.model_dump(mode="json")["value"] == 320
    assert isinstance(option.model_dump(mode="json")["value"], int)


def test_resume_inspection_preserves_mixed_wire_aliases() -> None:
    raw = {
        "type": "resume_inspection",
        "pipeline_kind": "streaming",
        "outputPath": "D:/out.mp4",
        "input_path": "D:/in.mp4",
        "finalExists": True,
        "sidecarExists": True,
        "signatureMatch": True,
        "completedChunks": 2,
        "completedOutputFrames": 120,
        "nextSourceFrame": 60,
        "totalOutputFrames": 240,
    }
    result = generated.ResumeInspectionResult.model_validate(raw)
    assert result.model_dump(by_alias=True, mode="json") == raw


def test_task_error_codes_match_neutral_backend_contract() -> None:
    schema = json.loads((SCHEMA_DIR / "backend-error-codes.schema.json").read_text(encoding="utf-8"))
    assert set(schema["enum"]) == {code.value for code in TaskErrorCode}
