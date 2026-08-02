"""Render Rust protocol, event, error, and persistence bindings."""

from __future__ import annotations

from typing import Any

from .context import CONTRACTS, _pascal_case
from .schema_tools import load_json as _load


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
        "mod application_defaults;",
        "mod backend_oneshot;",
        "mod backend_task_envelope;",
        "mod model_assets;",
        "mod persistence_versions;",
        "mod task_events;",
        "",
        "pub(crate) use crate::models::TaskControlKind;",
        "pub(crate) use application_defaults::DEFAULT_RIFE_MODEL_VERSION;",
        "pub(crate) use backend_oneshot::{",
        *export_lines,
        "};",
        "pub(crate) use model_assets::{",
        "    ModelAssetVariant, REAL_RAWVSR_BASICVSR_LICENSE_PATH, REAL_RAWVSR_BASICVSR_NOTICE_PATH,",
        "    REAL_RAWVSR_BASICVSR_VARIANTS,",
        "};",
        "pub(crate) use persistence_versions::{",
        "    ENVIRONMENT_CACHE_SCHEMA_VERSION, WORKBENCH_PRESET_SCHEMA_VERSION,",
        "};",
        "pub(crate) use task_events::TaskEventName;",
        "",
    ]
    return "\n".join(lines)
