#!/usr/bin/env python3
"""Generate and verify language bindings from the neutral contracts."""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_json_pointer(document: Any, pointer: str, *, ref: str) -> Any:
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


def _schema_string_values(property_schema: dict[str, Any], source: dict[str, Any], *, ref: str) -> set[str]:
    resolved = property_schema
    local_ref = property_schema.get("$ref")
    if isinstance(local_ref, str):
        location, separator, fragment = local_ref.partition("#")
        if location:
            return set()
        resolved_value = _resolve_json_pointer(source, fragment if separator else "", ref=f"{ref}: {local_ref}")
        if not isinstance(resolved_value, dict):
            return set()
        resolved = resolved_value
    const = resolved.get("const")
    if isinstance(const, str):
        return {const}
    enum = resolved.get("enum")
    return {value for value in enum or [] if isinstance(value, str)}


def _validate_contract_references(
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
                _resolve_json_pointer(target, fragment, ref=f"{source_name}: {ref}")
        for child in value.values():
            _validate_contract_references(
                child,
                source_name=source_name,
                source_schema=source_schema,
                schemas=schemas,
            )
    elif isinstance(value, list):
        for child in value:
            _validate_contract_references(
                child,
                source_name=source_name,
                source_schema=source_schema,
                schemas=schemas,
            )


def _validate_explicit_object_boundaries(
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
            _validate_explicit_object_boundaries(
                child,
                source_name=source_name,
                pointer=f"{pointer}/{escaped_key}",
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_explicit_object_boundaries(
                child,
                source_name=source_name,
                pointer=f"{pointer}/{index}",
            )


def validate_contracts() -> dict[str, Any]:
    schemas = sorted(CONTRACTS.glob("*.schema.json"))
    if not schemas:
        raise RuntimeError("contracts directory contains no JSON schemas")
    loaded_schemas = {path.name: _load(path) for path in schemas}
    for path in schemas:
        schema = loaded_schemas[path.name]
        Draft202012Validator.check_schema(schema)
        _validate_explicit_object_boundaries(schema, source_name=path.name)
        _validate_contract_references(
            schema,
            source_name=path.name,
            source_schema=schema,
            schemas=loaded_schemas,
        )

    manifest_schema = _load(CONTRACTS / "ipc-manifest.schema.json")
    manifest = _load(CONTRACTS / "ipc-manifest.json")
    Draft202012Validator(manifest_schema).validate(manifest)
    names = [command["name"] for command in manifest["commands"]]
    events = [event["name"] for event in manifest["events"]]
    if len(names) != len(set(names)):
        raise RuntimeError("IPC manifest contains duplicate command names")
    if len(events) != len(set(events)):
        raise RuntimeError("IPC manifest contains duplicate event names")

    backend_entries = [*manifest["backendTaskStream"], *manifest["backendOneShotCommands"]]
    envelope_names = [entry["envelope"] for entry in backend_entries]
    if len(envelope_names) != len(set(envelope_names)):
        raise RuntimeError("IPC manifest contains duplicate backend envelope names")
    one_shot_subcommands = [entry["subcommand"] for entry in manifest["backendOneShotCommands"]]
    if len(one_shot_subcommands) != len(set(one_shot_subcommands)):
        raise RuntimeError("IPC manifest contains duplicate backend one-shot subcommands")
    one_shot_commands = [entry["ipcCommand"] for entry in manifest["backendOneShotCommands"]]
    if len(one_shot_commands) != len(set(one_shot_commands)):
        raise RuntimeError("IPC manifest contains duplicate backend one-shot IPC commands")
    unknown_commands = sorted(set(one_shot_commands) - set(names))
    if unknown_commands:
        raise RuntimeError(f"backend one-shot entries reference unknown IPC commands: {unknown_commands}")

    boundary_definitions = json.loads(_render_boundary_schema())["$defs"]
    for entry in backend_entries:
        schema_name, pointer, source, payload = _resolve_manifest_schema_ref(entry["schemaRef"])
        if payload.get("type") != "object" or payload.get("additionalProperties") is not False:
            raise RuntimeError(f"backend envelope payload must be a strict object: {entry['schemaRef']}")
        expected_name = pointer.rsplit("/", 1)[-1] if pointer else source.get("title")
        if expected_name != entry["payload"]:
            raise RuntimeError(
                f"backend envelope payload name mismatch for {entry['schemaRef']}: "
                f"manifest={entry['payload']}, schema={expected_name}"
            )
        if entry["payload"] not in boundary_definitions:
            raise RuntimeError(f"backend envelope payload is missing from boundary schema: {entry['payload']}")
        type_schema = payload.get("properties", {}).get("type")
        if isinstance(type_schema, dict):
            values = _schema_string_values(type_schema, source, ref=f"{schema_name}{pointer}")
            if values != {entry["envelope"]}:
                raise RuntimeError(
                    f"backend envelope discriminator mismatch for {entry['schemaRef']}: "
                    f"manifest={entry['envelope']}, schema={sorted(values)}"
                )

    backend_codes = set(_load(CONTRACTS / "backend-error-codes.schema.json")["enum"])
    shell_codes = set(_load(CONTRACTS / "shell-error-codes.schema.json")["enum"])
    union_codes = set(_load(CONTRACTS / "error-codes.schema.json")["enum"])
    if union_codes != backend_codes | shell_codes:
        raise RuntimeError("error-codes.schema.json must be exactly the union of the backend and shell subsets")
    return manifest


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise RuntimeError(f"contract generator failed ({completed.returncode}): {' '.join(command)}")


def _generate_python_contracts(schema: Path, output: Path) -> None:
    _run(
        [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(schema),
            "--input-file-type",
            "jsonschema",
            "--output",
            str(output),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--target-python-version",
            "3.12",
            "--type-mappings",
            "integer+uint32=default",
            "integer+uint64=default",
            "--snake-case-field",
            "--allow-population-by-field-name",
            "--extra-fields",
            "forbid",
            "--use-standard-collections",
            "--use-union-operator",
            "--use-generic-base-class",
            "--use-default-kwarg",
            "--capitalise-enum-members",
            "--disable-timestamp",
            "--formatters",
            "ruff-format",
        ],
        cwd=ROOT,
    )
    _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--quiet",
            "--config",
            str(ROOT / "ruff.toml"),
            str(output),
        ],
        cwd=ROOT,
    )


def _generate_typescript(schema: Path, output: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required to generate TypeScript contracts")
    _run(
        [
            npm,
            "exec",
            "--",
            "json2ts",
            "-i",
            str(schema),
            "-o",
            str(output),
            "--bannerComment",
            f"/* Generated from contracts/{schema.name}. Do not edit. */",
        ],
        cwd=ROOT / "frontend",
    )


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


def _render_ipc_contract(manifest: dict[str, Any]) -> str:
    imported_types = sorted(
        {
            type_name.removesuffix("[]").removesuffix("|null")
            for command in manifest["commands"]
            for type_name in [*command["args"].values(), command["result"]]
            if type_name not in {"boolean", "string", "string[]", "string|null", "void"}
        }
    )
    lines = [
        "/* Generated from contracts/ipc-manifest.json. Do not edit. */",
        "",
    ]
    if imported_types:
        lines.extend(
            [
                "import type {",
                *(f"  {name}," for name in imported_types),
                "} from '@/types/protocol'",
            ]
        )
    lines.extend(["", "interface IpcCommandArgs {"])
    for command in manifest["commands"]:
        args = command["args"]
        shape = "undefined" if not args else "{ " + "; ".join(f"{name}: {kind}" for name, kind in args.items()) + " }"
        lines.append(f"  {command['name']}: {shape}")
    lines.extend(["}", "", "export type IpcCommand = keyof IpcCommandArgs", "", "interface IpcCommandResult {"])
    lines.extend(f"  {command['name']}: {command['result']}" for command in manifest["commands"])
    lines.extend(
        [
            "}",
            "",
            "export type IpcInvokeArgs<C extends IpcCommand> = IpcCommandArgs[C]",
            "export type IpcInvokeResult<C extends IpcCommand> = IpcCommandResult[C]",
            "",
        ]
    )
    return "\n".join(lines)


def _render_rust_manifest(manifest: dict[str, Any]) -> str:
    names = ",\n".join(f'    "{command["name"]}"' for command in manifest["commands"])
    return (
        "// Generated from contracts/ipc-manifest.json. Do not edit.\n"
        f"pub(crate) const APP_COMMAND_NAMES: &[&str] = &[\n{names},\n];\n"
    )


def _render_rust_oneshot_contracts(manifest: dict[str, Any]) -> str:
    one_shot_arms: list[str] = []
    for entry in manifest["backendOneShotCommands"]:
        _schema_name, _pointer, _source, payload = _resolve_manifest_schema_ref(entry["schemaRef"])
        preserve = "type" in payload.get("properties", {})
        rust_bool = "true" if preserve else "false"
        one_shot_arms.extend(
            (
                f'        "{entry["ipcCommand"]}" => Some(BackendOneShotContract {{',
                f'            subcommand: "{entry["subcommand"]}",',
                f'            envelope: "{entry["envelope"]}",',
                f"            preserve_discriminator: {rust_bool},",
                "        }),",
            )
        )
    lines = [
        "// Generated from contracts/ipc-manifest.json. Do not edit.",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub(crate) struct BackendOneShotContract {",
        "    pub(crate) subcommand: &'static str,",
        "    pub(crate) envelope: &'static str,",
        "    pub(crate) preserve_discriminator: bool,",
        "}",
        "",
        "pub(crate) fn backend_oneshot_contract(ipc_command: &str) -> Option<BackendOneShotContract> {",
        "    match ipc_command {",
        *one_shot_arms,
        "        _ => None,",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def _render_rust_task_envelopes(manifest: dict[str, Any]) -> str:
    entries = manifest["backendTaskStream"]
    payloads = sorted({entry["payload"] for entry in entries})
    lines = [
        "// Generated from contracts/ipc-manifest.json. Do not edit.",
        "",
        "use serde::Deserialize;",
        "",
        "use crate::models::{",
        f"    {', '.join(payloads)},",
        "};",
        "",
        "#[derive(Debug, Clone, Deserialize)]",
        '#[serde(tag = "type")]',
        "pub(crate) enum BackendTaskEnvelope {",
        *(
            line
            for entry in entries
            for line in (
                f'    #[serde(rename = "{entry["envelope"]}")]',
                f"    {_pascal_case(entry['envelope'])}({entry['payload']}),",
            )
        ),
        "}",
        "",
    ]
    return "\n".join(lines)


def _pascal_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in value.replace("_", "-").split("-"))


def _render_typescript_events(manifest: dict[str, Any]) -> str:
    events = manifest["events"]
    constants = manifest["protocolConstants"]
    payloads = sorted({event["payload"] for event in events})
    lines = [
        "/* Generated from contracts/ipc-manifest.json. Do not edit. */",
        "",
        "import type {",
        *(f"  {payload}," for payload in payloads),
        "} from '@/types/generated/contracts'",
        "",
        "export const TASK_EVENT_NAMES = {",
        *(f"  {_pascal_case(event['name'])}: '{event['name']}'," for event in events),
        "} as const",
        "",
        "export type TaskEventName = (typeof TASK_EVENT_NAMES)[keyof typeof TASK_EVENT_NAMES]",
        "",
        "export interface TaskEventPayloadMap {",
        *(f"  '{event['name']}': {event['payload']}" for event in events),
        "}",
        "",
        f"export const TERMINAL_PROGRESS_PREFIX = {constants['terminalProgressPrefix']!r}",
        "",
    ]
    return "\n".join(lines)


def _render_python_protocol_constants(manifest: dict[str, Any]) -> str:
    prefix = manifest["protocolConstants"]["terminalProgressPrefix"]
    backend_entries = [*manifest["backendTaskStream"], *manifest["backendOneShotCommands"]]
    payload_metadata: list[tuple[dict[str, Any], list[str], bool]] = []
    for entry in backend_entries:
        _schema_name, _pointer, _source, payload = _resolve_manifest_schema_ref(entry["schemaRef"])
        required = set(payload.get("required", []))
        optional_fields = sorted(
            name for name in payload.get("properties", {}) if name not in required and name != "type"
        )
        payload_metadata.append((entry, optional_fields, "type" in payload.get("properties", {})))
    lines = [
        '"""Generated from contracts/ipc-manifest.json. Do not edit."""',
        "",
        "from enum import StrEnum",
        "",
        "from app.generated import contracts as _contracts",
        "",
        "",
        "class BackendEnvelopeType(StrEnum):",
        *(f"    {entry['envelope'].upper()} = {json.dumps(entry['envelope'])}" for entry in backend_entries),
        "",
        "",
        f"TERMINAL_PROGRESS_PREFIX = {json.dumps(prefix)}",
        "",
        "BACKEND_ENVELOPE_PAYLOAD_TYPES = {",
        *(
            f"    BackendEnvelopeType.{entry['envelope'].upper()}: _contracts.{entry['payload']},"
            for entry in backend_entries
        ),
        "}",
        "",
        "BACKEND_ENVELOPE_OPTIONAL_FIELDS = {",
        *(
            f"    BackendEnvelopeType.{entry['envelope'].upper()}: frozenset({json.dumps(optional_fields)}),"
            for entry, optional_fields, _preserves_discriminator in payload_metadata
        ),
        "}",
        "",
        "BACKEND_ENVELOPE_PRESERVES_DISCRIMINATOR = frozenset(",
        "    {",
        *(
            f"        BackendEnvelopeType.{entry['envelope'].upper()},"
            for entry, _optional_fields, preserves_discriminator in payload_metadata
            if preserves_discriminator
        ),
        "    }",
        ")",
        "",
    ]
    return "\n".join(lines)


def _render_rust_events(manifest: dict[str, Any]) -> str:
    events = manifest["events"]
    variants = [(_pascal_case(event["name"]), event["name"]) for event in events]
    lines = [
        "// Generated from contracts/ipc-manifest.json. Do not edit.",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "#[allow(clippy::enum_variant_names)]",
        "pub(crate) enum TaskEventName {",
        *(f"    {variant}," for variant, _ in variants),
        "}",
        "",
        "impl TaskEventName {",
        "    pub(crate) const fn as_str(self) -> &'static str {",
        "        match self {",
        *(f'            Self::{variant} => "{name}",' for variant, name in variants),
        "        }",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def _render_rust_persistence_versions() -> str:
    definitions = _load(CONTRACTS / "persistence.schema.json")["$defs"]
    environment_version = definitions["EnvironmentCacheEntry"]["properties"]["schemaVersion"]["const"]
    preset_version = definitions["WorkbenchPresetEntry"]["properties"]["schemaVersion"]["const"]
    return (
        "// Generated from contracts/persistence.schema.json. Do not edit.\n"
        f"pub(crate) const ENVIRONMENT_CACHE_SCHEMA_VERSION: u64 = {environment_version};\n"
        f"pub(crate) const WORKBENCH_PRESET_SCHEMA_VERSION: u64 = {preset_version};\n"
    )


def _compare_or_write(target: Path, generated: Path | str, *, check: bool) -> bool:
    content = generated.read_text(encoding="utf-8") if isinstance(generated, Path) else generated
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    if current == content:
        return True
    if check:
        diff = difflib.unified_diff(
            current.splitlines(),
            content.splitlines(),
            fromfile=str(target.relative_to(ROOT)),
            tofile="generated",
            lineterm="",
        )
        sys.stderr.write("\n".join(diff) + "\n")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of updating stale generated files")
    args = parser.parse_args()
    manifest = validate_contracts()

    with tempfile.TemporaryDirectory(prefix="vp-contracts-") as temp:
        temp_dir = Path(temp)
        boundary_output = temp_dir / "boundary.schema.json"
        boundary_output.write_text(_render_boundary_schema(), encoding="utf-8", newline="\n")
        python_output = temp_dir / "contracts.py"
        typescript_output = temp_dir / "contracts.ts"
        _generate_python_contracts(boundary_output, python_output)
        _generate_typescript(boundary_output, typescript_output)
        outputs: tuple[tuple[Path, Path | str], ...] = (
            (ROOT / "backend/app/generated/contracts.py", python_output),
            (
                ROOT / "contracts/boundary.schema.json",
                boundary_output,
            ),
            (ROOT / "contracts/ndjson.schema.json", _render_ndjson_schema(manifest)),
            (
                ROOT / "frontend/src/types/generated/contracts.ts",
                typescript_output,
            ),
            (ROOT / "frontend/src/lib/ipc/contract.ts", _render_ipc_contract(manifest)),
            (
                ROOT / "frontend/src/types/protocol/events.ts",
                _render_typescript_events(manifest),
            ),
            (
                ROOT / "backend/app/generated/protocol_constants.py",
                _render_python_protocol_constants(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/ipc_manifest.rs",
                _render_rust_manifest(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/backend_oneshot.rs",
                _render_rust_oneshot_contracts(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/backend_task_envelope.rs",
                _render_rust_task_envelopes(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/task_events.rs",
                _render_rust_events(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/persistence_versions.rs",
                _render_rust_persistence_versions(),
            ),
        )
        results = [_compare_or_write(target, generated, check=args.check) for target, generated in outputs]
        clean = all(results)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
