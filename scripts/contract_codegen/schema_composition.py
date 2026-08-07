"""Compose canonical and target-specific JSON Schemas."""

from __future__ import annotations

import copy
import json
from typing import Any

from .context import CONTRACTS, _resolve_manifest_schema_ref
from .model_assets import model_asset_protocol_values
from .schema_tools import load_json as _load


_BOUNDARY_SCHEMA_FILES = (
    "task-request.schema.json",
    "workbench-preset.schema.json",
    "task-progress.schema.json",
    "task-completed.schema.json",
    "task-error.schema.json",
    "backend-task-error.schema.json",
    "task-log.schema.json",
    "task-cancelled.schema.json",
    "resume-status.schema.json",
    "resume-inspection.schema.json",
    "video-info.schema.json",
    "environment.schema.json",
    "task-control.schema.json",
    "error-codes.schema.json",
    "backend-error-codes.schema.json",
    "shell-error-codes.schema.json",
    "persistence.schema.json",
    "runtime-config.schema.json",
)

_INLINE_BOUNDARY_KEY = "x-vp-boundary-inline"


def _schema_catalog() -> dict[str, dict[str, Any]]:
    return {
        path.name: _load(path)
        for path in sorted(CONTRACTS.glob("*.schema.json"))
        if path.name != "boundary.schema.json"
    }


def _external_ref_target(ref: str, catalog: dict[str, dict[str, Any]]) -> tuple[str, str] | None:
    if not ref.startswith("./"):
        return None
    location, separator, fragment = ref[2:].partition("#")
    if location not in catalog:
        raise RuntimeError(f"contract reference target does not exist: {ref}")
    if not separator or not fragment:
        title = catalog[location].get("title")
        if not isinstance(title, str) or not title:
            raise RuntimeError(f"{location} requires a title for aggregate generation")
        return location, title
    prefix = "/$defs/"
    if not fragment.startswith(prefix):
        raise RuntimeError(f"unsupported aggregate contract reference: {ref}")
    definition_name = fragment.removeprefix(prefix).replace("~1", "/").replace("~0", "~")
    if definition_name not in catalog[location].get("$defs", {}):
        raise RuntimeError(f"contract reference definition does not exist: {ref}")
    return location, definition_name


def _rewrite_contract_refs(value: Any, catalog: dict[str, dict[str, Any]]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            target = _external_ref_target(ref, catalog)
            if target is not None:
                _, definition_name = target
                value["$ref"] = f"#/$defs/{definition_name}"
        for child in value.values():
            _rewrite_contract_refs(child, catalog)
    elif isinstance(value, list):
        for child in value:
            _rewrite_contract_refs(child, catalog)


def _external_schema_dependencies(value: Any, catalog: dict[str, dict[str, Any]]) -> set[str]:
    dependencies: set[str] = set()
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            target = _external_ref_target(ref, catalog)
            if target is not None:
                dependencies.add(target[0])
        for child in value.values():
            dependencies.update(_external_schema_dependencies(child, catalog))
    elif isinstance(value, list):
        for child in value:
            dependencies.update(_external_schema_dependencies(child, catalog))
    return dependencies


def _inline_boundary_definitions(value: Any, source_schema: dict[str, Any]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            definition_name = ref.removeprefix("#/$defs/")
            definition = source_schema.get("$defs", {}).get(definition_name)
            if isinstance(definition, dict) and definition.get(_INLINE_BOUNDARY_KEY) is True:
                replacement = {
                    key: copy.deepcopy(child) for key, child in definition.items() if key != _INLINE_BOUNDARY_KEY
                }
                siblings = {key: child for key, child in value.items() if key != "$ref"}
                value.clear()
                value.update(replacement)
                value.update(siblings)
        for child in value.values():
            _inline_boundary_definitions(child, source_schema)
    elif isinstance(value, list):
        for child in value:
            _inline_boundary_definitions(child, source_schema)


def _make_objects_strict(value: Any) -> None:
    if isinstance(value, dict):
        schema_type = value.get("type")
        is_object = schema_type == "object" or (isinstance(schema_type, list) and "object" in schema_type)
        if is_object and "additionalProperties" not in value:
            value["additionalProperties"] = False
        for child in value.values():
            _make_objects_strict(child)
    elif isinstance(value, list):
        for child in value:
            _make_objects_strict(child)


def _render_boundary_schema() -> str:
    definitions: dict[str, Any] = {}
    catalog = _schema_catalog()
    visited: set[str] = set()

    def add_definition(name: str, definition: Any, source: str) -> None:
        if isinstance(definition, dict) and definition.get(_INLINE_BOUNDARY_KEY) is True:
            return
        prepared = copy.deepcopy(definition)
        _inline_boundary_definitions(prepared, catalog[source])
        _rewrite_contract_refs(prepared, catalog)
        _make_objects_strict(prepared)
        existing = definitions.get(name)
        if existing is not None and existing != prepared:
            raise RuntimeError(f"conflicting boundary definition {name!r} while merging {source}")
        definitions[name] = prepared

    def add_schema(schema_name: str) -> None:
        if schema_name in visited:
            return
        visited.add(schema_name)
        schema = catalog[schema_name]
        for dependency in sorted(_external_schema_dependencies(schema, catalog)):
            add_schema(dependency)
        for name, definition in schema.get("$defs", {}).items():
            add_definition(name, definition, schema_name)
        title = schema.get("title")
        if not isinstance(title, str) or not title:
            raise RuntimeError(f"{schema_name} requires a title for aggregate generation")
        root = {
            key: copy.deepcopy(value)
            for key, value in schema.items()
            if key not in {"$schema", "$id", "$defs", "title"}
        }
        if root:
            root_ref = root.get("$ref") if len(root) == 1 else None
            if isinstance(root_ref, str):
                target = _external_ref_target(root_ref, catalog)
                if target is not None:
                    target_schema_name, target_definition = target
                    target_schema = catalog[target_schema_name]
                    if target_definition == target_schema.get("title"):
                        root = {
                            key: copy.deepcopy(value)
                            for key, value in target_schema.items()
                            if key not in {"$schema", "$id", "$defs", "title"}
                        }
            add_definition(title, root, schema_name)

    for schema_name in _BOUNDARY_SCHEMA_FILES:
        add_schema(schema_name)

    properties = {name: {"$ref": f"#/$defs/{name}"} for name in sorted(definitions)}
    aggregate = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://vp-workbench.local/contracts/boundary.schema.json",
        "title": "VpBoundaryContracts",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
        "$defs": {name: definitions[name] for name in sorted(definitions)},
    }
    return json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n"


def _render_typescript_boundary_schema() -> str:
    """Remove the Rust/Python-only runtime transport wrapper from the Vue target."""

    aggregate = json.loads(_render_boundary_schema())
    runtime_bundle = "RuntimeConfigBundle"
    aggregate["properties"].pop(runtime_bundle)
    aggregate["required"].remove(runtime_bundle)
    aggregate["$defs"].pop(runtime_bundle)
    return json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n"


def _render_ndjson_schema(manifest: dict[str, Any]) -> str:
    variants = [*manifest["backendTaskStream"], *manifest["backendOneShotCommands"]]
    one_of: list[dict[str, Any]] = []
    for variant in variants:
        schema_name, pointer, _source, payload = _resolve_manifest_schema_ref(variant["schemaRef"])
        event_type = variant["envelope"]
        properties = {
            property_name: {
                "$ref": f"./{schema_name}#{pointer}/properties/{property_name}",
            }
            for property_name in payload["properties"]
            if property_name != "type"
        }
        properties["type"] = {"const": event_type}
        one_of.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": [*(name for name in payload.get("required", []) if name != "type"), "type"],
            }
        )
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://vp-workbench.local/contracts/ndjson.schema.json",
        "title": "Backend NDJSON envelope",
        "oneOf": one_of,
    }
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def _render_stage_worker_schema(model_assets: dict[str, Any]) -> str:
    """Compose the Python-only worker contract without remote references."""
    schema = copy.deepcopy(_load(CONTRACTS / "stage-worker.schema.json"))
    backend_codes = copy.deepcopy(_load(CONTRACTS / "backend-error-codes.schema.json"))
    filter_step = copy.deepcopy(_load(CONTRACTS / "filter-step.schema.json"))
    inference_engine = copy.deepcopy(_load(CONTRACTS / "inference-engine.schema.json"))
    tensor_backend = copy.deepcopy(_load(CONTRACTS / "tensor-backend.schema.json"))
    schema["$defs"]["BackendTaskErrorCode"] = {
        key: value for key, value in backend_codes.items() if key not in {"$schema", "$id", "title"}
    }
    schema["$defs"]["InferenceEngine"] = {
        key: value for key, value in inference_engine.items() if key not in {"$schema", "$id", "title"}
    }
    schema["$defs"]["TensorBackend"] = {
        key: value for key, value in tensor_backend.items() if key not in {"$schema", "$id", "title"}
    }
    for name, definition in filter_step["$defs"].items():
        schema["$defs"][name] = definition
    schema["$defs"]["FilterStep"] = {
        key: value for key, value in filter_step.items() if key not in {"$schema", "$id", "title", "$defs"}
    }

    external_refs = {
        "./backend-error-codes.schema.json": "BackendTaskErrorCode",
        "./filter-step.schema.json": "FilterStep",
        "./inference-engine.schema.json": "InferenceEngine",
        "./tensor-backend.schema.json": "TensorBackend",
    }

    protocol_values = model_asset_protocol_values(model_assets)

    def rewrite(value: Any) -> None:
        if isinstance(value, dict):
            asset_field = value.pop("x-vp-model-assets", None)
            if asset_field is not None:
                values = protocol_values[asset_field]
                value.update({"const": values[0]} if len(values) == 1 else {"enum": list(values)})
            ref = value.get("$ref")
            if ref in external_refs:
                value["$ref"] = f"#/$defs/{external_refs[ref]}"
            for child in value.values():
                rewrite(child)
        elif isinstance(value, list):
            for child in value:
                rewrite(child)

    rewrite(schema)
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
