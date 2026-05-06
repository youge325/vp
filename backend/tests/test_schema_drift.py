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


@pytest.mark.parametrize("schema_name,model_cls", _MODEL_MAP.items())
def test_property_names_and_types_match(schema_name: str, model_cls: type) -> None:
    rust_path = SCHEMA_DIR / f"{schema_name}.schema.json"
    assert rust_path.exists(), f"Rust schema missing: {rust_path}"

    rust_schema = json.loads(rust_path.read_text(encoding="utf-8"))
    py_schema = model_cls.model_json_schema()

    rust_props = _collect_props(rust_schema)
    py_props = _collect_props(py_schema)

    assert set(rust_props.keys()) == set(py_props.keys()), (
        f"Property name mismatch for {schema_name}: rust={set(rust_props.keys())} vs py={set(py_props.keys())}"
    )

    for name in rust_props:
        rust_type = _type_token(rust_props[name])
        py_type = _type_token(py_props[name])
        assert rust_type == py_type, f"Type mismatch for {schema_name}.{name}: rust={rust_type} vs py={py_type}"

        rust_req = _is_required(rust_schema, name)
        py_req = _is_required(py_schema, name)
        assert rust_req == py_req, f"Required mismatch for {schema_name}.{name}: rust={rust_req} vs py={py_req}"
