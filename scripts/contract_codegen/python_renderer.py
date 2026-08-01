"""Generate and render Python contract bindings."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from .context import CONTRACTS, ROOT, _resolve_manifest_schema_ref
from .process_tools import _run
from .schema_tools import load_json as _load


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
