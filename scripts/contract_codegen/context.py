"""Shared paths and naming helpers for contract generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema_tools import load_json as _load
from .schema_tools import resolve_json_pointer as _resolve_json_pointer

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


def _resolve_manifest_schema_ref(schema_ref: str) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    location, separator, fragment = schema_ref.partition("#")
    if not location.startswith("./"):
        raise RuntimeError(f"backend envelope schemaRef must be local: {schema_ref}")
    schema_name = location[2:]
    source_path = CONTRACTS / schema_name
    if not source_path.is_file():
        raise RuntimeError(f"backend envelope schemaRef does not exist: {schema_ref}")
    source = _load(source_path)
    pointer = fragment if separator else ""
    target = _resolve_json_pointer(source, pointer, ref=schema_ref)
    if not isinstance(target, dict):
        raise RuntimeError(f"backend envelope schemaRef must resolve to an object schema: {schema_ref}")
    return schema_name, pointer, source, target


def _pascal_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in value.replace("_", "-").split("-"))
