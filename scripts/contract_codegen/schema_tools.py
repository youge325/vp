"""Reusable JSON Schema loading, reference, and strictness validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_json_pointer(document: Any, pointer: str, *, ref: str) -> Any:
    current = document
    if not pointer:
        return current
    if not pointer.startswith("/"):
        raise RuntimeError(f"contract reference uses an unsupported fragment: {ref}")
    for encoded_part in pointer[1:].split("/"):
        part = encoded_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise RuntimeError(f"contract reference target does not exist: {ref}")
    return current


def validate_contract_references(
    value: Any,
    *,
    source_name: str,
    source_schema: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            location, separator, fragment = ref.partition("#")
            if location:
                if not location.startswith("./") or location[2:] not in schemas:
                    raise RuntimeError(f"{source_name} has an invalid contract reference: {ref}")
                target = schemas[location[2:]]
            else:
                target = source_schema
            if separator:
                resolve_json_pointer(target, fragment, ref=f"{source_name}: {ref}")
        for child in value.values():
            validate_contract_references(
                child,
                source_name=source_name,
                source_schema=source_schema,
                schemas=schemas,
            )
    elif isinstance(value, list):
        for child in value:
            validate_contract_references(
                child,
                source_name=source_name,
                source_schema=source_schema,
                schemas=schemas,
            )


def validate_explicit_object_boundaries(
    value: Any,
    *,
    source_name: str,
    pointer: str = "#",
) -> None:
    if isinstance(value, dict):
        schema_type = value.get("type")
        is_object = schema_type == "object" or (isinstance(schema_type, list) and "object" in schema_type)
        if is_object and "additionalProperties" not in value:
            raise RuntimeError(f"{source_name} object schema must declare additionalProperties explicitly: {pointer}")
        for key, child in value.items():
            escaped_key = key.replace("~", "~0").replace("/", "~1")
            validate_explicit_object_boundaries(
                child,
                source_name=source_name,
                pointer=f"{pointer}/{escaped_key}",
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_explicit_object_boundaries(
                child,
                source_name=source_name,
                pointer=f"{pointer}/{index}",
            )
