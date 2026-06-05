"""Compare Python pydantic schemas against the Rust-generated JSON Schema files.

These tests guard against silent field-name or type drift when one side is
updated but the other is forgotten.  They do **not** enforce identical
schema-metadata (e.g. ``title``, ``description``) — only the structural
contract that matters at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.errors import TaskErrorCode
from app.models import (
    AnimeConfig,
    DecodeConfig,
    EncodeConfig,
    FilterStep,
    InterpolationConfig,
    OutputConfig,
    PostprocessConfig,
    PreprocessConfig,
    RateControlConfig,
    SuperResolutionConfig,
    WorkflowConfig,
)
from app.protocol.payloads import (
    ResumeStatusPayload,
    TaskCompletedPayload,
    TaskErrorPayload,
    TaskProgressPayload,
)

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src-tauri" / "schemas"

_MODEL_MAP: dict[str, type] = {
    "anime_config": AnimeConfig,
    "decode_config": DecodeConfig,
    "encode_config": EncodeConfig,
    "filter_step": FilterStep,
    "interpolation_config": InterpolationConfig,
    "output_config": OutputConfig,
    "postprocess_config": PostprocessConfig,
    "preprocess_config": PreprocessConfig,
    "rate_control_config": RateControlConfig,
    "super_resolution_config": SuperResolutionConfig,
    "workflow_config": WorkflowConfig,
}

_PAYLOAD_MODEL_MAP: dict[str, type] = {
    "resume_status_payload": ResumeStatusPayload,
    "task_completed_payload": TaskCompletedPayload,
    "task_error_payload": TaskErrorPayload,
    "task_progress_payload": TaskProgressPayload,
}

_FREEFORM_PAYLOAD_PROPS: dict[str, set[str]] = {
    "task_error_payload": {"details"},
    "task_progress_payload": {"metrics"},
}


def _collect_props(schema: dict) -> dict[str, dict]:
    """Flatten a schema into {camelCase_property: property_schema}."""
    props = schema.get("properties", {})
    defs = schema.get("$defs", {})
    # schemars nests sub-schemas under $defs; resolve $ref pointers
    result: dict[str, dict] = {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            # schemars may emit `true` for unconstrained types (e.g. serde_json::Value)
            result[name] = {"type": "any"}
        elif "$ref" in prop:
            ref_name = prop["$ref"].split("/")[-1]
            result[name] = defs.get(ref_name, {})
        else:
            result[name] = prop
    return result


def _is_required(schema: dict, prop_name: str) -> bool:
    return prop_name in schema.get("required", [])


def _type_token(prop_schema: dict) -> str:
    """Return a normalised type token for drift comparison."""
    if not prop_schema or prop_schema == {"type": "any"}:
        return "any"
    if "anyOf" in prop_schema:
        types: list[str] = []
        for branch in prop_schema["anyOf"]:
            bt = branch.get("type")
            if bt:
                types.append(bt)
        return " | ".join(sorted(types))
    t = prop_schema.get("type")
    if t is None:
        return "any"
    if isinstance(t, list):
        return " | ".join(sorted(t))
    if "$ref" in prop_schema:
        return "object"
    return str(t)


def _enum_values(prop_schema: dict) -> set[str] | None:
    """Return string enum values when the schema constrains a field by enum."""
    if "enum" in prop_schema:
        return {str(value) for value in prop_schema["enum"]}
    if "anyOf" in prop_schema:
        values: set[str] = set()
        for branch in prop_schema["anyOf"]:
            branch_values = _enum_values(branch)
            if branch_values is not None:
                values.update(branch_values)
        return values or None
    return None


def _assert_schema_matches_python_model(
    schema_name: str,
    model_cls: type,
    *,
    freeform_props: set[str] | None = None,
) -> None:
    rust_path = SCHEMA_DIR / f"{schema_name}.schema.json"
    assert rust_path.exists(), f"Rust schema missing: {rust_path}"

    rust_schema = json.loads(rust_path.read_text(encoding="utf-8"))
    py_schema = model_cls.model_json_schema()
    freeform_props = freeform_props or set()

    rust_props = _collect_props(rust_schema)
    py_props = _collect_props(py_schema)

    assert set(rust_props.keys()) == set(py_props.keys()), (
        f"Property name mismatch for {schema_name}: rust={set(rust_props.keys())} vs py={set(py_props.keys())}"
    )

    for name in rust_props:
        rust_req = _is_required(rust_schema, name)
        py_req = _is_required(py_schema, name)
        assert rust_req == py_req, f"Required mismatch for {schema_name}.{name}: rust={rust_req} vs py={py_req}"

        if name in freeform_props:
            continue

        rust_type = _type_token(rust_props[name])
        py_type = _type_token(py_props[name])
        assert rust_type == py_type, f"Type mismatch for {schema_name}.{name}: rust={rust_type} vs py={py_type}"

        rust_enum = _enum_values(rust_props[name])
        py_enum = _enum_values(py_props[name])
        assert rust_enum == py_enum, f"Enum mismatch for {schema_name}.{name}: rust={rust_enum} vs py={py_enum}"


@pytest.mark.parametrize("schema_name,model_cls", _MODEL_MAP.items())
def test_property_names_and_types_match(schema_name: str, model_cls: type) -> None:
    _assert_schema_matches_python_model(schema_name, model_cls)


@pytest.mark.parametrize("schema_name,model_cls", _PAYLOAD_MODEL_MAP.items())
def test_ndjson_payload_schema_matches_rust(schema_name: str, model_cls: type) -> None:
    _assert_schema_matches_python_model(
        schema_name,
        model_cls,
        freeform_props=_FREEFORM_PAYLOAD_PROPS.get(schema_name),
    )


def test_task_error_codes_match_rust() -> None:
    """Python ``TaskErrorCode`` enum must contain exactly the codes Rust emits.

    The Rust-side source of truth is ``frontend/src-tauri/src/models/task.rs``
    where ``TaskErrorCode`` derives ``JsonSchema``; schemars writes the
    snake_case variant strings into the generated JSON schema. This test
    fails fast when one side adds or removes a code without the other.
    """
    schema_path = SCHEMA_DIR / "task_error_payload.schema.json"
    assert schema_path.exists(), f"Rust schema missing: {schema_path}"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    rust_codes = set(schema["$defs"]["TaskErrorCode"]["enum"])
    python_codes = {code.value for code in TaskErrorCode}

    assert rust_codes == python_codes, (
        f"TaskErrorCode drift: only-in-rust={rust_codes - python_codes}, only-in-python={python_codes - rust_codes}"
    )
