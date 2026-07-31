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


def _validate_backend_cli_invocation(entry: dict[str, Any], boundary_definitions: dict[str, Any]) -> None:
    label = entry["ipcCommand"]
    stdin_payload = entry["stdinPayload"]
    stdin_field = entry["stdinField"]
    if (stdin_payload is None) != (stdin_field is None):
        raise RuntimeError(f"{label} must declare stdinPayload and stdinField together")

    flags: list[str] = []
    fields: list[str] = []
    for argument in entry["cliArguments"]:
        flag = argument["flag"]
        flags.append(flag)
        field = argument.get("field")
        value_type = argument.get("valueType")
        optional = argument.get("optional", False)
        if field is None:
            if value_type is not None or optional:
                raise RuntimeError(f"{label} literal flag {flag} cannot declare a value type or optionality")
            continue
        if value_type is None:
            raise RuntimeError(f"{label} valued flag {flag} must declare valueType")
        if value_type != "string" and value_type not in boundary_definitions:
            raise RuntimeError(f"{label} flag {flag} references unknown valueType {value_type}")
        fields.append(field)

    if len(flags) != len(set(flags)):
        raise RuntimeError(f"{label} contains duplicate CLI flags")
    if len(fields) != len(set(fields)):
        raise RuntimeError(f"{label} contains duplicate CLI input fields")
    if stdin_field in fields:
        raise RuntimeError(f"{label} stdin field must not also be encoded as a CLI argument")


def _manifest_type_name(type_expression: str) -> str | None:
    """Return the named boundary type carried by a manifest type expression."""

    value = type_expression.removesuffix("|null").removesuffix("[]")
    return value if value[:1].isupper() else None


def _referenced_boundary_types(
    type_name: str,
    boundary_definitions: dict[str, Any],
    *,
    include_root: bool = True,
) -> set[str]:
    """Collect named boundary types reachable through local definition refs."""

    discovered = {type_name} if include_root else set()
    pending = [type_name]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        definition = boundary_definitions.get(current)
        if not isinstance(definition, dict):
            continue
        for node in _walk_json_values(definition):
            if not isinstance(node, dict):
                continue
            ref = node.get("$ref")
            if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
                continue
            referenced = ref.removeprefix("#/$defs/")
            if referenced in boundary_definitions and referenced not in discovered:
                discovered.add(referenced)
                pending.append(referenced)
    return discovered


def _walk_json_values(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_walk_json_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk_json_values(child))
    return values


def _property_schema_for_command_field(
    field: str,
    command: dict[str, Any],
    boundary_definitions: dict[str, Any],
) -> tuple[dict[str, Any], bool] | None:
    direct_type = command["args"].get(field)
    if direct_type == "string":
        return {"type": "string"}, True
    if direct_type is not None:
        direct_name = _manifest_type_name(direct_type)
        if direct_name is not None:
            return {"$ref": f"#/$defs/{direct_name}"}, True

    for argument_type in command["args"].values():
        type_name = _manifest_type_name(argument_type)
        if type_name is None:
            continue
        definition = boundary_definitions.get(type_name, {})
        property_schema = definition.get("properties", {}).get(field)
        if isinstance(property_schema, dict):
            return property_schema, field in definition.get("required", [])
    return None


def _schema_matches_cli_value_type(
    schema: dict[str, Any],
    value_type: str,
    *,
    optional: bool,
    required: bool,
) -> bool:
    variants = schema.get("anyOf")
    candidates = variants if isinstance(variants, list) else [schema]
    if not all(isinstance(candidate, dict) for candidate in candidates):
        return False
    expected = {"type": "string"} if value_type == "string" else {"$ref": f"#/$defs/{value_type}"}
    value_candidates = [candidate for candidate in candidates if candidate != {"type": "null"}]
    null_count = sum(candidate == {"type": "null"} for candidate in candidates)
    if value_candidates != [expected]:
        return False
    if optional:
        return not required and null_count == 1 and len(candidates) == 2
    return required and null_count == 0 and len(candidates) == 1


def _validate_backend_command_bindings(
    manifest: dict[str, Any],
    boundary_definitions: dict[str, Any],
) -> None:
    """Bind backend transport declarations to their public IPC command shapes."""

    commands = {command["name"]: command for command in manifest["commands"]}
    process = manifest["backendProcessCommand"]
    process_command = commands[process["ipcCommand"]]
    if process_command["result"] != "void":
        raise RuntimeError("backend process IPC command must return void and complete through task events")

    entries = [process, *manifest["backendOneShotCommands"]]
    for entry in entries:
        command = commands[entry["ipcCommand"]]
        for argument in entry["cliArguments"]:
            field = argument.get("field")
            if field is None:
                continue
            property_binding = _property_schema_for_command_field(field, command, boundary_definitions)
            if property_binding is None:
                raise RuntimeError(
                    f"{entry['ipcCommand']} CLI field {field} is not reachable from its IPC command arguments"
                )
            property_schema, required = property_binding
            if not _schema_matches_cli_value_type(
                property_schema,
                argument["valueType"],
                optional=argument.get("optional", False),
                required=required,
            ):
                raise RuntimeError(
                    f"{entry['ipcCommand']} CLI field {field} type/optionality does not match its IPC command argument"
                )

        stdin_payload = entry["stdinPayload"]
        if stdin_payload is not None:
            input_types = {
                referenced
                for type_expression in command["args"].values()
                if (type_name := _manifest_type_name(type_expression)) is not None
                for referenced in _referenced_boundary_types(type_name, boundary_definitions)
            }
            payload_dependencies = _referenced_boundary_types(
                stdin_payload,
                boundary_definitions,
                include_root=False,
            )
            if not payload_dependencies or not payload_dependencies <= input_types:
                raise RuntimeError(
                    f"{entry['ipcCommand']} stdin payload is not derivable from its IPC command arguments"
                )

    for entry in manifest["backendOneShotCommands"]:
        command = commands[entry["ipcCommand"]]
        result_name = _manifest_type_name(command["result"])
        result_types = (
            _referenced_boundary_types(result_name, boundary_definitions) if result_name is not None else set()
        )
        if entry["payload"] not in result_types:
            raise RuntimeError(
                f"{entry['ipcCommand']} backend payload {entry['payload']} is not represented by "
                f"its IPC result {command['result']}"
            )


def _validate_termination_reap_bindings(manifest: dict[str, Any]) -> None:
    """Require every child-process command to bind its reap deadline to a declared limit."""

    entries = [
        (manifest["backendProcessCommand"]["subcommand"], manifest["backendProcessCommand"]),
        *((entry["subcommand"], entry) for entry in manifest["backendOneShotCommands"]),
        (manifest["stageWorkerCommand"]["subcommand"], manifest["stageWorkerCommand"]),
    ]
    limits = manifest["protocolLimits"]
    for subcommand, entry in entries:
        limit_name = entry["deadlines"]["terminationReapLimit"]
        if limit_name not in limits:
            raise RuntimeError(
                f"{subcommand} termination/reap deadline references an unknown protocol limit: {limit_name}"
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

    process_command = manifest["backendProcessCommand"]
    if process_command["ipcCommand"] not in names:
        raise RuntimeError("backend process entry references an unknown IPC command")
    if process_command["ipcCommand"] in one_shot_commands:
        raise RuntimeError("backend process and one-shot entries must use distinct IPC commands")
    stream_discriminants = [entry["envelope"] for entry in manifest["backendTaskStream"]]
    if process_command["discriminants"] != stream_discriminants:
        raise RuntimeError("backend process discriminants must exactly match backendTaskStream order")
    if process_command["deadlines"]["totalMs"] is not None:
        raise RuntimeError("the long-running process command must not declare a total timeout")
    if any(entry["deadlines"]["totalMs"] is None for entry in manifest["backendOneShotCommands"]):
        raise RuntimeError("every backend one-shot command must declare a total timeout")

    stage_worker = manifest["stageWorkerCommand"]
    if stage_worker["subcommand"] in {process_command["subcommand"], *one_shot_subcommands}:
        raise RuntimeError("stage-worker subcommand must be distinct from desktop backend commands")
    stage_worker_definitions = json.loads(_render_stage_worker_schema())["$defs"]
    config_payload = stage_worker["input"]["configPayload"]
    if config_payload not in stage_worker_definitions:
        raise RuntimeError(f"stage-worker config payload is missing from its schema: {config_payload}")
    declared_events = stage_worker["output"]["stderrPayloads"]
    schema_events = [
        name
        for name, definition in stage_worker_definitions.items()
        if isinstance(definition, dict)
        and isinstance(definition.get("properties", {}).get("type"), dict)
        and "const" in definition["properties"]["type"]
    ]
    if declared_events != schema_events:
        raise RuntimeError(
            "stage-worker stderr payloads must exactly match typed schema events: "
            f"manifest={declared_events}, schema={schema_events}"
        )
    _validate_termination_reap_bindings(manifest)

    boundary_definitions = json.loads(_render_boundary_schema())["$defs"]
    if process_command["stdinPayload"] not in boundary_definitions:
        raise RuntimeError("backend process stdin payload is missing from boundary schema")
    _validate_backend_cli_invocation(process_command, boundary_definitions)
    for entry in manifest["backendOneShotCommands"]:
        stdin_payload = entry["stdinPayload"]
        if stdin_payload is not None and stdin_payload not in boundary_definitions:
            raise RuntimeError(f"backend one-shot stdin payload is missing from boundary schema: {stdin_payload}")
        _validate_backend_cli_invocation(entry, boundary_definitions)
    _validate_backend_command_bindings(manifest, boundary_definitions)
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


def _schema_allows_null(
    schema: dict[str, Any],
    definitions: dict[str, Any],
    seen_refs: frozenset[str] = frozenset(),
) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null" or (isinstance(schema_type, list) and "null" in schema_type):
        return True
    if "const" in schema and schema["const"] is None:
        return True
    if None in schema.get("enum", []):
        return True
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/") and ref not in seen_refs:
        target = definitions.get(ref.removeprefix("#/$defs/"))
        if isinstance(target, dict):
            return _schema_allows_null(target, definitions, seen_refs | {ref})
    for keyword in ("anyOf", "oneOf"):
        variants = schema.get(keyword)
        if isinstance(variants, list) and any(
            isinstance(variant, dict) and _schema_allows_null(variant, definitions, seen_refs) for variant in variants
        ):
            return True
    all_of = schema.get("allOf")
    return bool(all_of) and all(
        isinstance(variant, dict) and _schema_allows_null(variant, definitions, seen_refs) for variant in all_of
    )


def _render_python_target_schema(schema: dict[str, Any]) -> str:
    """Annotate optional non-null JSON Schema fields for strict Pydantic generation."""

    prepared = copy.deepcopy(schema)
    definitions = prepared.get("$defs", {})

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" and isinstance(value.get("properties"), dict):
                required = set(value.get("required", []))
                for name, property_schema in value["properties"].items():
                    if (
                        name not in required
                        and isinstance(property_schema, dict)
                        and not _schema_allows_null(property_schema, definitions)
                    ):
                        property_schema["nullable"] = False
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(prepared)
    return json.dumps(prepared, ensure_ascii=False, indent=2) + "\n"


def _generate_python_contracts(schema: Path, output: Path, *, collapse_root_models: bool = False) -> None:
    generation_dir = schema.parent / f"python-{schema.stem}"
    generation_dir.mkdir()
    generation_schema = generation_dir / schema.name
    generation_schema.write_text(
        _render_python_target_schema(json.loads(schema.read_text(encoding="utf-8"))),
        encoding="utf-8",
        newline="\n",
    )
    command = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(generation_schema),
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
        "--strict-types",
        "str",
        "bytes",
        "int",
        "float",
        "bool",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-generic-base-class",
        "--use-default-kwarg",
        "--strict-nullable",
        "--capitalise-enum-members",
        "--disable-timestamp",
        "--formatters",
        "ruff-format",
    ]
    if collapse_root_models:
        command.append("--collapse-root-models")
    _run(command, cwd=ROOT)
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


def _render_stage_worker_schema() -> str:
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

    def rewrite(value: Any) -> None:
        if isinstance(value, dict):
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
    process = manifest["backendProcessCommand"]
    event_payload = process["eventPayload"]
    limits = manifest["protocolLimits"]
    command_entries = [process, *manifest["backendOneShotCommands"]]
    payload_types = {
        process["stdinPayload"],
        *(entry["payload"] for entry in manifest["backendOneShotCommands"]),
        *(entry["stdinPayload"] for entry in manifest["backendOneShotCommands"] if entry["stdinPayload"] is not None),
    }
    boundary_definitions = json.loads(_render_boundary_schema())["$defs"]
    enum_argument_types = sorted(
        {
            argument["valueType"]
            for entry in command_entries
            for argument in entry["cliArguments"]
            if argument.get("valueType") not in (None, "string")
        }
    )
    enum_import = (
        f"use crate::models::task::{enum_argument_types[0]};"
        if len(enum_argument_types) == 1
        else f"use crate::models::task::{{{', '.join(enum_argument_types)}}};"
    )

    def invocation_name(entry: dict[str, Any]) -> str:
        return f"{_pascal_case(entry['ipcCommand'])}Invocation"

    def rust_field_name(field: str) -> str:
        return "".join(f"_{character.lower()}" if character.isupper() else character for character in field).lstrip("_")

    def rust_field_type(argument: dict[str, Any]) -> str:
        value_type = "String" if argument["valueType"] == "string" else argument["valueType"]
        return f"Option<{value_type}>" if argument.get("optional", False) else value_type

    def render_argument_value(argument: dict[str, Any], value_expression: str) -> str:
        if argument["valueType"] == "string":
            return f"{value_expression}.clone()"
        helper = rust_field_name(argument["valueType"])
        return f"{helper}_argument({value_expression}).to_string()"

    def render_invocation(entry: dict[str, Any]) -> list[str]:
        fields = [
            (rust_field_name(argument["field"]), rust_field_type(argument))
            for argument in entry["cliArguments"]
            if "field" in argument
        ]
        if entry["stdinField"] is not None:
            fields.append((rust_field_name(entry["stdinField"]), entry["stdinPayload"]))
        name = invocation_name(entry)
        if not fields:
            return [
                "#[doc(hidden)]",
                "#[derive(Clone, Copy, Debug, Default)]",
                f"pub(crate) struct {name};",
                "",
            ]
        return [
            "#[doc(hidden)]",
            f"pub(crate) struct {name} {{",
            *(f"    pub(crate) {field}: {field_type}," for field, field_type in fields),
            "}",
            "",
        ]

    def render_arguments(entry: dict[str, Any]) -> list[str]:
        if not entry["cliArguments"]:
            return ["        Vec::new()", "    }"]
        arguments = entry["cliArguments"]
        optional_index = next(
            (index for index, argument in enumerate(arguments) if argument.get("optional", False)),
            len(arguments),
        )
        prefix = arguments[:optional_index]
        tail = arguments[optional_index:]
        prefix_values: list[str] = []
        for argument in prefix:
            prefix_values.append(f"{json.dumps(argument['flag'])}.to_string()")
            if "field" in argument:
                rust_field = rust_field_name(argument["field"])
                prefix_values.append(render_argument_value(argument, f"invocation.{rust_field}"))
        if prefix_values:
            mutable = "mut " if tail else ""
            compact = f"        let {mutable}arguments = vec![{', '.join(prefix_values)}];"
            body = (
                [compact]
                if len(compact) <= 100
                else [
                    f"        let {mutable}arguments = vec![",
                    *(f"            {value}," for value in prefix_values),
                    "        ];",
                ]
            )
        else:
            body = ["        let mut arguments = Vec::new();"]

        for argument in tail:
            flag = json.dumps(argument["flag"])
            field = argument.get("field")
            if field is None:
                body.append(f"        arguments.push({flag}.to_string());")
                continue
            rust_field = rust_field_name(field)
            if argument.get("optional", False):
                body.extend(
                    [
                        f"        if let Some(value) = &invocation.{rust_field} {{",
                        f"            arguments.push({flag}.to_string());",
                        f"            arguments.push({render_argument_value(argument, 'value')});",
                        "        }",
                    ]
                )
            else:
                body.extend(
                    [
                        f"        arguments.push({flag}.to_string());",
                        f"        arguments.push({render_argument_value(argument, f'invocation.{rust_field}')});",
                    ]
                )
        body.extend(["        arguments", "    }"])
        return body

    lines = [
        "// Generated from contracts/ipc-manifest.json. Do not edit.",
        "",
        "use std::time::Duration;",
        "",
        f"use crate::generated::backend_task_envelope::{event_payload};",
        *([enum_import] if enum_argument_types else []),
        "use crate::models::{",
        f"    {', '.join(sorted(payload_types))},",
        "};",
        "",
        f"pub(crate) const NDJSON_LINE_LIMIT_BYTES: usize = {limits['ndjsonLineBytes']};",
        f"pub(crate) const ONE_SHOT_STDOUT_LIMIT_BYTES: usize = {limits['oneShotStdoutBytes']};",
        f"pub(crate) const STDERR_TAIL_LIMIT_BYTES: usize = {limits['stderrTailBytes']};",
        f"pub(crate) const ERROR_SUMMARY_LIMIT_BYTES: usize = {limits['errorSummaryBytes']};",
        "",
        "mod private {",
        "    pub(crate) trait Sealed {}",
        "}",
        "",
        "#[derive(serde::Serialize)]",
        "pub(crate) enum NoStdinPayload {}",
        "",
        "pub(crate) trait BackendCommandSpec: private::Sealed {",
        "    type Invocation;",
        "    const SUBCOMMAND: &'static str;",
        "    fn arguments(invocation: &Self::Invocation) -> Vec<String>;",
        "}",
        "",
        "pub(crate) trait BackendProcessSpec: BackendCommandSpec {",
        "    type Input: serde::Serialize;",
        "    type Event;",
        "",
        "    const STDIN_TIMEOUT: Duration;",
        "    const TERMINATION_TIMEOUT: Duration;",
        "    fn stdin_payload(invocation: &Self::Invocation) -> &Self::Input;",
        "}",
        "",
        "pub(crate) trait BackendOneShotSpec: BackendCommandSpec {",
        "    type Input: serde::Serialize;",
        "    type Output;",
        "",
        "    const ENVELOPE: &'static str;",
        "    const PAYLOAD_NAME: &'static str;",
        "    const PRESERVE_DISCRIMINATOR: bool;",
        "    const STDIN_TIMEOUT: Duration;",
        "    const TOTAL_TIMEOUT: Duration;",
        "    const TERMINATION_TIMEOUT: Duration;",
        "    fn stdin_payload(invocation: &Self::Invocation) -> Option<&Self::Input>;",
        "}",
        "",
        *(
            line
            for value_type in enum_argument_types
            for line in [
                f"fn {rust_field_name(value_type)}_argument(value: &{value_type}) -> &'static str {{",
                "    match value {",
                *(
                    f'        {value_type}::{_pascal_case(value)} => "{value}",'
                    for value in boundary_definitions[value_type]["enum"]
                ),
                "    }",
                "}",
                "",
            ]
        ),
        *(line for entry in command_entries for line in render_invocation(entry)),
        f"pub(crate) struct {_pascal_case(process['ipcCommand'])}Spec;",
        "",
        f"impl private::Sealed for {_pascal_case(process['ipcCommand'])}Spec {{}}",
        "",
        f"impl BackendCommandSpec for {_pascal_case(process['ipcCommand'])}Spec {{",
        f"    type Invocation = {invocation_name(process)};",
        f"    const SUBCOMMAND: &'static str = {json.dumps(process['subcommand'])};",
        "",
        "    fn arguments(invocation: &Self::Invocation) -> Vec<String> {",
        *render_arguments(process),
        "}",
        "",
        f"impl BackendProcessSpec for {_pascal_case(process['ipcCommand'])}Spec {{",
        f"    type Input = {process['stdinPayload']};",
        f"    type Event = {event_payload};",
        "",
        f"    const STDIN_TIMEOUT: Duration = Duration::from_millis({process['deadlines']['stdinMs']});",
        f"    const TERMINATION_TIMEOUT: Duration = Duration::from_millis({limits[process['deadlines']['terminationReapLimit']]});",
        "",
        "    fn stdin_payload(invocation: &Self::Invocation) -> &Self::Input {",
        f"        &invocation.{rust_field_name(process['stdinField'])}",
        "    }",
        "}",
        "",
    ]
    for entry in manifest["backendOneShotCommands"]:
        _schema_name, _pointer, _source, payload = _resolve_manifest_schema_ref(entry["schemaRef"])
        spec_name = f"{_pascal_case(entry['ipcCommand'])}Spec"
        input_name = entry["stdinPayload"] or "NoStdinPayload"
        preserve = "true" if "type" in payload.get("properties", {}) else "false"
        lines.extend(
            [
                f"pub(crate) struct {spec_name};",
                "",
                f"impl private::Sealed for {spec_name} {{}}",
                "",
                f"impl BackendCommandSpec for {spec_name} {{",
                f"    type Invocation = {invocation_name(entry)};",
                f"    const SUBCOMMAND: &'static str = {json.dumps(entry['subcommand'])};",
                "",
                (
                    "    fn arguments(_invocation: &Self::Invocation) -> Vec<String> {"
                    if not entry["cliArguments"]
                    else "    fn arguments(invocation: &Self::Invocation) -> Vec<String> {"
                ),
                *render_arguments(entry),
                "}",
                "",
                f"impl BackendOneShotSpec for {spec_name} {{",
                f"    type Input = {input_name};",
                f"    type Output = {entry['payload']};",
                "",
                f"    const ENVELOPE: &'static str = {json.dumps(entry['envelope'])};",
                f"    const PAYLOAD_NAME: &'static str = {json.dumps(entry['payload'])};",
                f"    const PRESERVE_DISCRIMINATOR: bool = {preserve};",
                f"    const STDIN_TIMEOUT: Duration = Duration::from_millis({entry['deadlines']['stdinMs']});",
                f"    const TOTAL_TIMEOUT: Duration = Duration::from_millis({entry['deadlines']['totalMs']});",
                f"    const TERMINATION_TIMEOUT: Duration = Duration::from_millis({limits[entry['deadlines']['terminationReapLimit']]});",
                "",
                (
                    "    fn stdin_payload(invocation: &Self::Invocation) -> Option<&Self::Input> {"
                    if entry["stdinField"] is not None
                    else "    fn stdin_payload(_invocation: &Self::Invocation) -> Option<&Self::Input> {"
                ),
                (
                    f"        Some(&invocation.{rust_field_name(entry['stdinField'])})"
                    if entry["stdinField"] is not None
                    else "        None"
                ),
                "    }",
                "}",
                "",
            ]
        )
    return "\n".join(lines)


def _render_rust_error_code_conversion() -> str:
    backend_codes = _load(CONTRACTS / "backend-error-codes.schema.json")["enum"]
    lines = [
        "// Generated from contracts/backend-error-codes.schema.json. Do not edit.",
        "",
        "use super::boundary::{BackendTaskErrorCode, TaskErrorCode};",
        "",
        "pub(super) const fn backend_error_code_to_task_error_code(",
        "    code: BackendTaskErrorCode,",
        ") -> TaskErrorCode {",
        "    match code {",
        *(
            f"        BackendTaskErrorCode::{_pascal_case(code)} => TaskErrorCode::{_pascal_case(code)},"
            for code in backend_codes
        ),
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def _render_rust_task_envelopes(manifest: dict[str, Any]) -> str:
    entries = manifest["backendTaskStream"]
    envelope_type = manifest["backendProcessCommand"]["eventPayload"]
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
        f"pub(crate) enum {envelope_type} {{",
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
    constants = manifest["protocolConstants"]
    limits = manifest["protocolLimits"]
    stage_worker = manifest["stageWorkerCommand"]
    stage_worker_command = ", ".join(json.dumps(part) for part in stage_worker["command"])
    if len(stage_worker["command"]) == 1:
        stage_worker_command += ","
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
        "from app.generated.bootstrap_constants import (",
        "    ERROR_SUMMARY_LIMIT_BYTES as ERROR_SUMMARY_LIMIT_BYTES,",
        "    NDJSON_LINE_LIMIT_BYTES as NDJSON_LINE_LIMIT_BYTES,",
        ")",
        "",
        "",
        "class BackendEnvelopeType(StrEnum):",
        *(f"    {entry['envelope'].upper()} = {json.dumps(entry['envelope'])}" for entry in backend_entries),
        "",
        "",
        f"TERMINAL_PROGRESS_PREFIX = {json.dumps(constants['terminalProgressPrefix'])}",
        f"STAGE_WORKER_EVENT_PREFIX = {json.dumps(constants['stageWorkerEventPrefix'])}",
        f"STAGE_WORKER_COMMAND = ({stage_worker_command})",
        f"STAGE_WORKER_SUBCOMMAND = {json.dumps(stage_worker['subcommand'])}",
        f"STAGE_WORKER_CONFIG_FLAG = {json.dumps(stage_worker['configFlag'])}",
        f"ONE_SHOT_STDOUT_LIMIT_BYTES = {limits['oneShotStdoutBytes']}",
        f"STDERR_TAIL_LIMIT_BYTES = {limits['stderrTailBytes']}",
        f"TERMINATION_REAP_TIMEOUT_MS = {limits['terminationReapMs']}",
        "STAGE_WORKER_TERMINATION_REAP_TIMEOUT_MS = TERMINATION_REAP_TIMEOUT_MS",
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


def _render_python_bootstrap_constants(manifest: dict[str, Any]) -> str:
    codes = _load(CONTRACTS / "backend-error-codes.schema.json")["enum"]
    limits = manifest["protocolLimits"]
    return (
        '"""Generated import-safe bootstrap constants. Do not edit."""\n\n'
        f"NDJSON_LINE_LIMIT_BYTES = {limits['ndjsonLineBytes']}\n"
        f"ERROR_SUMMARY_LIMIT_BYTES = {limits['errorSummaryBytes']}\n\n"
        "BACKEND_TASK_ERROR_CODES = frozenset(\n"
        "    {\n" + "".join(f"        {json.dumps(code)},\n" for code in codes) + "    }\n"
        ")\n"
    )


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


def _render_rust_generated_mod(manifest: dict[str, Any]) -> str:
    one_shot_specs = [f"{_pascal_case(entry['ipcCommand'])}Spec" for entry in manifest["backendOneShotCommands"]]
    invocation_types = [
        f"{_pascal_case(entry['ipcCommand'])}Invocation"
        for entry in [manifest["backendProcessCommand"], *manifest["backendOneShotCommands"]]
    ]
    process_spec = f"{_pascal_case(manifest['backendProcessCommand']['ipcCommand'])}Spec"
    exports = [
        *sorted(
            [
                "BackendCommandSpec",
                "BackendOneShotSpec",
                "BackendProcessSpec",
                *invocation_types,
                *one_shot_specs,
                process_spec,
            ]
        ),
        *sorted(
            [
                "ERROR_SUMMARY_LIMIT_BYTES",
                "NDJSON_LINE_LIMIT_BYTES",
                "ONE_SHOT_STDOUT_LIMIT_BYTES",
                "STDERR_TAIL_LIMIT_BYTES",
            ]
        ),
    ]
    export_lines: list[str] = []
    current = "    "
    for export in exports:
        token = f"{export}, "
        if len(current) + len(token) > 100 and current.strip():
            export_lines.append(current.rstrip())
            current = "    "
        current += token
    if current.strip():
        export_lines.append(current.rstrip())
    lines = [
        "// Generated from repository contracts. Do not edit.",
        "mod backend_oneshot;",
        "mod backend_task_envelope;",
        "mod persistence_versions;",
        "mod task_events;",
        "",
        "pub(crate) use crate::models::TaskControlKind;",
        "pub(crate) use backend_oneshot::{",
        *export_lines,
        "};",
        "pub(crate) use persistence_versions::{",
        "    ENVIRONMENT_CACHE_SCHEMA_VERSION, WORKBENCH_PRESET_SCHEMA_VERSION,",
        "};",
        "pub(crate) use task_events::TaskEventName;",
        "",
    ]
    return "\n".join(lines)


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
        stage_worker_schema = temp_dir / "stage-worker.schema.json"
        stage_worker_schema.write_text(_render_stage_worker_schema(), encoding="utf-8", newline="\n")
        stage_worker_output = temp_dir / "stage_worker_contracts.py"
        typescript_schema_dir = temp_dir / "typescript"
        typescript_schema_dir.mkdir()
        typescript_schema = typescript_schema_dir / "boundary.schema.json"
        typescript_schema.write_text(_render_typescript_boundary_schema(), encoding="utf-8", newline="\n")
        typescript_output = temp_dir / "contracts.ts"
        _generate_python_contracts(boundary_output, python_output)
        _generate_python_contracts(stage_worker_schema, stage_worker_output, collapse_root_models=True)
        _generate_typescript(typescript_schema, typescript_output)
        outputs: tuple[tuple[Path, Path | str], ...] = (
            (ROOT / "backend/app/generated/contracts.py", python_output),
            (ROOT / "backend/app/generated/stage_worker_contracts.py", stage_worker_output),
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
                ROOT / "backend/app/generated/bootstrap_constants.py",
                _render_python_bootstrap_constants(manifest),
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
                ROOT / "frontend/src-tauri/src/models/generated_error_codes.rs",
                _render_rust_error_code_conversion(),
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
            (
                ROOT / "frontend/src-tauri/src/generated/mod.rs",
                _render_rust_generated_mod(manifest),
            ),
        )
        results = [_compare_or_write(target, generated, check=args.check) for target, generated in outputs]
        clean = all(results)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
