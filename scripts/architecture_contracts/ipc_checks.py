"""Cross-language IPC command-surface checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .graph_ast import _find_matching, _snake_to_camel, _split_top_level_commas
from .rules import ContractParseError, read_source, relative_path


@dataclass(frozen=True)
class ManifestCommand:
    args: dict[str, str]
    result: str


@dataclass(frozen=True)
class RustCommandSignature:
    args: dict[str, str]
    result: str


def _collect_manifest_commands(root: Path) -> dict[str, ManifestCommand]:
    path = root / "contracts/ipc-manifest.json"
    try:
        manifest = json.loads(read_source(path, root))
    except json.JSONDecodeError as exc:
        raise ContractParseError(f"invalid IPC manifest JSON: {exc}") from exc
    if manifest.get("schemaVersion") != 4:
        raise ContractParseError("unsupported contracts/ipc-manifest.json schemaVersion")
    commands = manifest.get("commands")
    if not isinstance(commands, list):
        raise ContractParseError("IPC manifest commands must be an array")
    result: dict[str, ManifestCommand] = {}
    for command in commands:
        if not isinstance(command, dict) or not isinstance(command.get("name"), str):
            raise ContractParseError("IPC manifest command entries require a string name")
        name = command["name"]
        args = command.get("args")
        if name in result:
            raise ContractParseError(f"duplicate IPC command in manifest: {name}")
        if not isinstance(args, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in args.items()
        ):
            raise ContractParseError(f"IPC manifest args for {name!r} must map names to type strings")
        result_type = command.get("result")
        if not isinstance(result_type, str):
            raise ContractParseError(f"IPC manifest result for {name!r} must be a type string")
        result[name] = ManifestCommand(args=args, result=result_type)
    return result


def _collect_permission_commands(root: Path) -> set[str]:
    path = root / "frontend/src-tauri/permissions/default.toml"
    tokens = set(re.findall(r'"(allow-[a-z-]+)"', read_source(path, root)))
    return {token.removeprefix("allow-").replace("-", "_") for token in tokens}


def _collect_frontend_invoke_commands(root: Path) -> set[str]:
    endpoint_dir = root / "frontend/src/lib/ipc/endpoints"
    if not endpoint_dir.is_dir():
        raise ContractParseError("missing reference root: frontend/src/lib/ipc/endpoints")
    pattern = re.compile(r"safeInvoke(?:<[^>]+>)?\(\s*['\"]([a-z_]+)['\"]")
    commands: set[str] = set()
    for path in sorted(endpoint_dir.rglob("*.ts")):
        commands.update(pattern.findall(read_source(path, root)))
    return commands


def _normalise_rust_type(raw_type: str) -> str:
    value = re.sub(r"\s+", "", raw_type)
    for prefix in ("crate::models::", "crate::generated::", "vp_workbench_lib::models::"):
        value = value.replace(prefix, "")
    return value.removeprefix("&")


def _collect_rust_command_signatures(root: Path) -> dict[str, RustCommandSignature]:
    tauri_src = root / "frontend/src-tauri/src"
    signatures: dict[str, RustCommandSignature] = {}
    command_attr = re.compile(r"^\s*#\s*\[\s*tauri::command\s*\]", re.MULTILINE)
    function_decl = re.compile(r"(?:#\[[^\]]+\]\s*)*pub(?:\s*\([^)]*\))?\s+(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)")

    for path in sorted(tauri_src.rglob("*.rs")):
        text = read_source(path, root)
        for attr_match in command_attr.finditer(text):
            fn_match = function_decl.search(text, attr_match.end())
            if not fn_match:
                raise ContractParseError(
                    f"could not parse tauri command after attribute in {relative_path(path, root)}"
                )
            command = fn_match.group(1)
            args_start = text.find("(", fn_match.end())
            if args_start < 0:
                raise ContractParseError(f"could not parse args for tauri command {command!r}")
            args_end = _find_matching(text, args_start, "(", ")")
            args: dict[str, str] = {}
            for parameter in _split_top_level_commas(text[args_start + 1 : args_end]):
                if ":" not in parameter:
                    continue
                raw_name, raw_type = parameter.split(":", 1)
                type_name = _normalise_rust_type(raw_type)
                if type_name.startswith(("AppHandle", "State<", "tauri::AppHandle", "tauri::State<")):
                    continue
                name = raw_name.strip().removeprefix("mut ").strip()
                wire_name = _snake_to_camel(name) if "_" in name else name
                args[wire_name] = type_name

            body_start = text.find("{", args_end)
            result_marker = text.find("Result", args_end, body_start)
            if body_start < 0 or result_marker < 0:
                raise ContractParseError(f"could not parse result for tauri command {command!r}")
            result_start = text.find("<", result_marker, body_start)
            if result_start < 0:
                raise ContractParseError(f"could not parse Result type for tauri command {command!r}")
            result_end = _find_matching(text, result_start, "<", ">")
            result_parts = _split_top_level_commas(text[result_start + 1 : result_end])
            if len(result_parts) != 2 or _normalise_rust_type(result_parts[1]) != "ShellError":
                raise ContractParseError(f"tauri command {command!r} must return Result<T, ShellError>")
            if command in signatures:
                raise ContractParseError(f"duplicate #[tauri::command] function: {command}")
            signatures[command] = RustCommandSignature(
                args=args,
                result=_normalise_rust_type(result_parts[0]),
            )
    return signatures


def _collect_registered_tauri_commands(root: Path) -> set[str]:
    path = root / "frontend/src-tauri/src/lib.rs"
    text = read_source(path, root)
    matches = list(re.finditer(r"tauri::generate_handler!\s*\[", text))
    if len(matches) != 1:
        raise ContractParseError("frontend/src-tauri/src/lib.rs must contain exactly one tauri::generate_handler! list")
    body_start = matches[0].end() - 1
    body_end = _find_matching(text, body_start, "[", "]")
    commands: set[str] = set()
    for entry in _split_top_level_commas(text[body_start + 1 : body_end]):
        command = entry.strip().split("::")[-1]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", command):
            raise ContractParseError(f"could not parse generate_handler entry: {entry!r}")
        if command in commands:
            raise ContractParseError(f"duplicate generate_handler entry: {command}")
        commands.add(command)
    return commands


def _manifest_type_to_rust(type_name: str) -> str:
    if type_name.endswith("|null"):
        return f"Option<{_manifest_type_to_rust(type_name.removesuffix('|null'))}>"
    if type_name.endswith("[]"):
        return f"Vec<{_manifest_type_to_rust(type_name.removesuffix('[]'))}>"
    primitive = {
        "boolean": "bool",
        "number": "f64",
        "string": "String",
        "void": "()",
    }
    return primitive.get(type_name, type_name)


def _collect_typed_ipc_contract_args(root: Path) -> dict[str, set[str]]:
    path = root / "frontend/src/lib/ipc/contract.ts"
    text = read_source(path, root)
    match = re.search(r"(?:export\s+)?interface\s+IpcCommandArgs\s*\{", text)
    if not match:
        raise ContractParseError("could not parse IpcCommandArgs in frontend IPC contract")
    body_start = text.find("{", match.start())
    body_end = _find_matching(text, body_start, "{", "}")
    command_args: dict[str, set[str]] = {}
    for line in text[body_start + 1 : body_end].splitlines():
        line = line.strip().rstrip(",;")
        if not line:
            continue
        line_match = re.match(r"([a-z_]+):\s*(.+)$", line)
        if not line_match:
            raise ContractParseError(f"could not parse IpcCommandArgs line: {line}")
        command, value = line_match.groups()
        value = value.strip()
        if value == "undefined":
            command_args[command] = set()
        elif value.startswith("{") and value.endswith("}"):
            command_args[command] = set(re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*:", value))
        else:
            raise ContractParseError(f"unsupported IpcCommandArgs shape for {command!r}: {value}")
    return command_args


def diff_command_surface(
    *,
    manifest: set[str],
    permissions: set[str],
    rust_args: dict[str, set[str]],
    handlers: set[str],
    invoke_args: set[str],
    contract_args: dict[str, set[str]],
) -> list[str]:
    issues: list[str] = []
    rust_commands = set(rust_args)
    frontend_commands = set(invoke_args)
    contract_commands = set(contract_args)
    comparisons = (
        ("permissions", permissions),
        ("rust", rust_commands),
        ("handlers", handlers),
        ("frontend", frontend_commands),
        ("contract", contract_commands),
    )
    for label, commands in comparisons:
        if commands != manifest:
            issues.append(
                f"command surface {label} drift: only-in-manifest={sorted(manifest - commands)}, "
                f"only-in-{label}={sorted(commands - manifest)}"
            )
    for command in sorted(manifest & rust_commands & contract_commands):
        if rust_args[command] != contract_args[command]:
            issues.append(
                f"IPC command args drift for `{command}`: "
                f"rust={sorted(rust_args[command])}, contract={sorted(contract_args[command])}"
            )
    return issues


def diff_command_types(
    manifest_commands: dict[str, ManifestCommand],
    rust_signatures: dict[str, RustCommandSignature],
) -> list[str]:
    issues: list[str] = []
    for command in sorted(set(manifest_commands) & set(rust_signatures)):
        manifest_command = manifest_commands[command]
        rust_signature = rust_signatures[command]
        for argument in sorted(set(manifest_command.args) & set(rust_signature.args)):
            expected = _manifest_type_to_rust(manifest_command.args[argument])
            actual = rust_signature.args[argument]
            if actual != expected:
                issues.append(f"IPC command type drift for `{command}.{argument}`: manifest={expected}, rust={actual}")
        expected_result = _manifest_type_to_rust(manifest_command.result)
        if rust_signature.result != expected_result:
            issues.append(
                f"IPC command result drift for `{command}`: manifest={expected_result}, rust={rust_signature.result}"
            )
    return issues


def _check_command_surface(root: Path) -> list[str]:
    manifest_commands = _collect_manifest_commands(root)
    manifest = set(manifest_commands)
    permissions = _collect_permission_commands(root)
    rust_signatures = _collect_rust_command_signatures(root)
    rust_args = {command: set(signature.args) for command, signature in rust_signatures.items()}
    handlers = _collect_registered_tauri_commands(root)
    invoke_commands = _collect_frontend_invoke_commands(root)
    contract_args = _collect_typed_ipc_contract_args(root)
    issues = diff_command_surface(
        manifest=manifest,
        permissions=permissions,
        rust_args=rust_args,
        handlers=handlers,
        invoke_args=invoke_commands,
        contract_args=contract_args,
    )
    for command in sorted(manifest & set(contract_args)):
        manifest_args = set(manifest_commands[command].args)
        if manifest_args != contract_args[command]:
            issues.append(
                f"IPC manifest args drift for `{command}`: "
                f"manifest={sorted(manifest_args)}, contract={sorted(contract_args[command])}"
            )
    issues.extend(diff_command_types(manifest_commands, rust_signatures))

    permission_path = root / "frontend/src-tauri/permissions/default.toml"
    raw_tokens = set(re.findall(r'"(allow-[a-z-]+)"', read_source(permission_path, root)))
    expected_tokens = {f"allow-{command.replace('_', '-')}" for command in manifest}
    if raw_tokens != expected_tokens:
        issues.append(
            "Tauri permission tokens drift: "
            f"missing={sorted(expected_tokens - raw_tokens)}, extra={sorted(raw_tokens - expected_tokens)}"
        )
    return issues
