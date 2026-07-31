"""Regression tests for neutral contract composition and generated aggregates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_contracts import (  # noqa: E402
    _render_boundary_schema,
    _render_ndjson_schema,
    _render_python_protocol_constants,
    _render_rust_oneshot_contracts,
    _render_rust_task_envelopes,
    _render_typescript_events,
    _validate_explicit_object_boundaries,
    validate_contracts,
)


def _load(name: str) -> dict[str, object]:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_source_contract_references_resolve_and_preserve_named_filter_boundaries() -> None:
    validate_contracts()
    aggregate = json.loads(_render_boundary_schema())
    definitions = aggregate["$defs"]

    assert definitions["PreprocessConfig"] == definitions["PostprocessConfig"]
    assert definitions["PreprocessConfig"]["type"] == "object"
    assert definitions["PreprocessConfig"]["properties"]["filters"]["items"] == {"$ref": "#/$defs/FilterStep"}


def test_contract_validation_rejects_implicit_object_openness() -> None:
    with pytest.raises(RuntimeError, match="additionalProperties.*#/properties/nested"):
        _validate_explicit_object_boundaries(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {},
                    }
                },
            },
            source_name="example.schema.json",
        )


def test_ndjson_schema_reuses_payload_property_schemas() -> None:
    schema = json.loads(_render_ndjson_schema(validate_contracts()))
    expected_sources = (
        ("task-progress.schema.json", ""),
        ("task-completed.schema.json", ""),
        ("backend-task-error.schema.json", ""),
        ("resume-status.schema.json", ""),
        ("video-info.schema.json", ""),
        ("environment.schema.json", "/$defs/EnvironmentCheckResult"),
        ("resume-inspection.schema.json", ""),
    )

    for variant, (source_name, pointer) in zip(schema["oneOf"], expected_sources, strict=True):
        for property_name, property_schema in variant["properties"].items():
            if property_name != "type":
                assert property_schema == {"$ref": f"./{source_name}#{pointer}/properties/{property_name}"}

    assert [variant["properties"]["type"]["const"] for variant in schema["oneOf"]] == [
        "progress",
        "completed",
        "error",
        "resume_status",
        "info",
        "check",
        "resume_inspection",
    ]


def test_protocol_constants_are_generated_from_the_manifest() -> None:
    manifest = validate_contracts()

    assert 'TERMINAL_PROGRESS_PREFIX = "[VP_PROGRESS]"' in _render_python_protocol_constants(manifest)
    assert "TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'" in _render_typescript_events(manifest)


def test_rust_backend_protocol_adapters_are_generated_from_the_manifest() -> None:
    manifest = validate_contracts()
    one_shot = _render_rust_oneshot_contracts(manifest)
    task_envelopes = _render_rust_task_envelopes(manifest)

    assert '"inspect_video" => Some(BackendOneShotContract {' in one_shot
    assert 'subcommand: "info"' in one_shot
    assert '"info" => Some(BackendOneShotContract {' not in one_shot
    assert task_envelopes.count("#[serde(rename = ") == 4
    assert "Progress(TaskProgressPayload)" in task_envelopes
    assert "ResumeStatus(ResumeStatusPayload)" in task_envelopes


def test_ndjson_external_references_validate_real_envelopes() -> None:
    schema = _load("ndjson.schema.json")
    base_uri = "https://vp-workbench.local/contracts/"
    registry = Registry().with_resources(
        (
            f"{base_uri}{path.name}",
            Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))),
        )
        for path in CONTRACTS.glob("*.schema.json")
    )
    validator = Draft202012Validator(schema, registry=registry)
    envelopes = [
        {
            "type": "progress",
            "current": 1,
            "total": 2,
            "percent": 50.0,
            "stage": "Encoding",
            "stageIndex": 1,
            "stageTotal": 1,
        },
        {
            "type": "completed",
            "outputPath": "output.mp4",
            "processedFrames": 20,
            "timeSeconds": 1.5,
        },
        {
            "type": "error",
            "code": "invalid_input",
            "message": "invalid video",
            "details": None,
        },
        {
            "type": "resume_status",
            "resumed": True,
            "completedChunks": 2,
            "completedOutputFrames": 10,
            "startSourceFrame": 5,
            "totalOutputFrames": 20,
        },
        {
            "type": "info",
            "fps": 24.0,
            "width": 1920,
            "height": 1080,
            "videoCodec": "h264",
        },
        {
            "type": "check",
            "ffmpeg": {
                "available": True,
                "hwaccels": [],
                "encoderProfiles": [],
                "decoderProfiles": [],
            },
            "gpu": {"adapters": []},
            "tensorEngines": {"pytorch": [], "paddle": [], "onnx": []},
            "interpolationAlgorithms": [],
            "superResolutionAlgorithms": [],
            "runtimeMode": "external",
        },
        {
            "type": "resume_inspection",
            "pipeline_kind": "streaming",
            "outputPath": "output.mp4",
            "input_path": "input.mp4",
            "finalExists": False,
            "sidecarExists": True,
            "signatureMatch": True,
            "completedChunks": 2,
            "completedOutputFrames": 10,
            "nextSourceFrame": 5,
            "totalOutputFrames": 20,
        },
    ]

    for envelope in envelopes:
        validator.validate(envelope)

    with pytest.raises(ValidationError):
        validator.validate({**envelopes[0], "unexpected": 0})
    with pytest.raises(ValidationError):
        validator.validate({**envelopes[-1], "completedChunks": -1})
