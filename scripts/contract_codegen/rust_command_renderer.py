"""Render sealed Rust backend command specifications."""

from __future__ import annotations

import json
from typing import Any

from .context import _pascal_case, _resolve_manifest_schema_ref
from .schema_composition import _render_boundary_schema


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
