"""Validate source schemas and the IPC manifest before rendering."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from .context import CONTRACTS, _resolve_manifest_schema_ref
from .schema_composition import _render_boundary_schema, _render_stage_worker_schema
from .schema_tools import (
    load_json as _load,
    resolve_json_pointer as _resolve_json_pointer,
    validate_contract_references as _validate_contract_references,
    validate_explicit_object_boundaries as _validate_explicit_object_boundaries,
)


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
