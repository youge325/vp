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
    schema = json.loads(_render_ndjson_schema())
    expected_sources = (
        "task-progress.schema.json",
        "task-completed.schema.json",
        "backend-task-error.schema.json",
        "resume-status.schema.json",
    )

    for variant, source_name in zip(schema["oneOf"], expected_sources, strict=True):
        for property_name, property_schema in variant["properties"].items():
            if property_name != "type":
                assert property_schema == {"$ref": f"./{source_name}#/properties/{property_name}"}


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
    progress = {
        "type": "progress",
        "current": 1,
        "total": 2,
        "percent": 50.0,
        "stage": "Encoding",
        "stageIndex": 1,
        "stageTotal": 1,
    }

    validator.validate(progress)
    with pytest.raises(ValidationError):
        validator.validate({**progress, "unexpected": 0})
