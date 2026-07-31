"""Semantic architecture checks that cannot be expressed as text rules."""

from __future__ import annotations

import ast
import json
import re
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .catalog import RULES
from .python_ast import literal_name_registry, literal_string_keys, literal_string_pair_registry
from .rules import ContractParseError, read_source, relative_path, run_rules


def _parse_python(path: Path, root: Path) -> ast.Module:
    try:
        return ast.parse(read_source(path, root), filename=relative_path(path, root))
    except SyntaxError as exc:
        raise ContractParseError(f"could not parse Python source {relative_path(path, root)}: {exc.msg}") from exc


def _find_matching(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    raise ContractParseError(f"could not find matching {close_char!r}")


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    pairs = {"<": ">", "(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    for index, char in enumerate(text):
        if char in pairs:
            depth += 1
        elif char in closers:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _snake_to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


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
    if manifest.get("schemaVersion") != 3:
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


def _collect_python_dict_keys(text: str, symbol: str) -> set[str]:
    return set(literal_string_keys(ast.parse(text), symbol))


def _collect_python_name_registry(text: str, symbol: str) -> dict[str, str]:
    """Read an exact literal ``str -> local name`` registry."""
    return literal_name_registry(ast.parse(text), symbol)


def _static_descriptor_value(node: ast.expr) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
        and not node.keywords
    ):
        return frozenset(ast.literal_eval(node.args[0]))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_GeometryPolicy":
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            raise ContractParseError("_GeometryPolicy requires one literal geometry kind")
        if any(keyword.arg != "fixed_scale_factor" for keyword in node.keywords):
            raise ContractParseError("_GeometryPolicy contains an unsupported field")
        fixed_scale = next(
            (
                _static_descriptor_value(keyword.value)
                for keyword in node.keywords
                if keyword.arg == "fixed_scale_factor"
            ),
            None,
        )
        return {
            "kind": node.args[0].value,
            "fixed_scale_factor": fixed_scale,
        }
    raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR must use statically readable descriptor values")


def _collect_paddlegan_descriptor(root: Path) -> dict[str, object]:
    path = root / "backend/app/catalog/stage_descriptors.py"
    tree = _parse_python(path, root)
    assignment = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                isinstance(node.target, ast.Name)
                if isinstance(node, ast.AnnAssign)
                else len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            )
            and (node.target.id if isinstance(node, ast.AnnAssign) else node.targets[0].id)
            == "PADDLEGAN_STAGE_DESCRIPTOR"
        ),
        None,
    )
    if assignment is None:
        raise ContractParseError("could not find PADDLEGAN_STAGE_DESCRIPTOR in the neutral catalog")
    value = assignment.value
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "StageDescriptor":
        raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR must construct StageDescriptor")
    if value.args:
        raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR must use keyword-only StageDescriptor fields")
    descriptor = {
        keyword.arg: _static_descriptor_value(keyword.value) for keyword in value.keywords if keyword.arg is not None
    }
    if len(descriptor) != len(value.keywords):
        raise ContractParseError("PADDLEGAN_STAGE_DESCRIPTOR may not use expanded keyword arguments")
    return descriptor


def diff_paddlegan_catalog_contract(
    backend_specs: set[str],
    factory_models: set[str],
    descriptor: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    missing_factories = backend_specs - factory_models
    extra_factories = factory_models - backend_specs
    if missing_factories or extra_factories:
        issues.append(
            "PaddleGAN VSR factory drift: "
            f"missing-factories={sorted(missing_factories)}, extra-factories={sorted(extra_factories)}"
        )
    expected_descriptor = {
        "execution_mode": "sequence",
        "requires_file_pipeline": True,
        "geometry": {"kind": "fixed_scale", "fixed_scale_factor": 4.0},
        "supported_backends": frozenset({"paddle"}),
        "factory_key": "paddlegan_vsr",
        "model_kind": "paddlegan_vsr",
    }
    if descriptor != expected_descriptor:
        issues.append(f"PaddleGAN VSR descriptor fields drift: expected={expected_descriptor!r}, actual={descriptor!r}")
    return issues


def _check_paddlegan_metadata(root: Path) -> list[str]:
    catalog = root / "backend/app/catalog/paddlegan_models.py"
    specs = _collect_python_dict_keys(read_source(catalog, root), "PADDLEGAN_VSR_SPECS")
    descriptor = _collect_paddlegan_descriptor(root)
    factory_path = root / "backend/app/algorithms/paddle/paddlegan_vsr/model_factory.py"
    factories = _collect_python_dict_keys(read_source(factory_path, root), "_MODEL_FACTORIES")
    return diff_paddlegan_catalog_contract(specs, factories, descriptor)


def _check_python_algorithm_factory_registry(root: Path) -> list[str]:
    factory_path = root / "backend/app/processing/streaming/stage_worker_factory.py"
    factory_source = read_source(factory_path, root)
    factories = _collect_python_name_registry(factory_source, "_ALGORITHM_FACTORIES")
    descriptor_path = root / "backend/app/catalog/stage_descriptors.py"
    descriptor_tree = _parse_python(descriptor_path, root)
    expected_keys: set[str] = set()
    for statement in descriptor_tree.body:
        value = statement.value if isinstance(statement, (ast.Assign, ast.AnnAssign)) else None
        if (
            not isinstance(value, ast.Call)
            or not isinstance(value.func, ast.Name)
            or value.func.id != "StageDescriptor"
        ):
            continue
        factory_keyword = next((keyword for keyword in value.keywords if keyword.arg == "factory_key"), None)
        if factory_keyword is None or not isinstance(factory_keyword.value, ast.Constant):
            raise ContractParseError("StageDescriptor factory_key must be a static string")
        factory_key = factory_keyword.value.value
        if not isinstance(factory_key, str):
            raise ContractParseError("StageDescriptor factory_key must be a static string")
        if factory_key != "filter_chain":
            expected_keys.add(factory_key)
    issues: list[str] = []
    if set(factories) != expected_keys:
        issues.append(
            "stage-worker algorithm factory registry drift: "
            f"expected-keys={sorted(expected_keys)}, actual-keys={sorted(factories)}"
        )

    tree = ast.parse(factory_source, filename=relative_path(factory_path, root))
    definitions = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing_definitions = set(factories.values()) - set(definitions)
    if missing_definitions:
        issues.append(f"stage-worker factory registry references missing functions: {sorted(missing_definitions)}")
    for factory_name in sorted(set(factories.values()) & set(definitions)):
        lazy_modules = {
            node.module
            for node in ast.walk(definitions[factory_name])
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
        } | {
            alias.name
            for node in ast.walk(definitions[factory_name])
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name.startswith("app.")
        }
        if not lazy_modules:
            issues.append(f"stage-worker registered factory has no direct lazy app import: {factory_name}")
    return issues


def _decorator_name(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _find_unconsumed_python_boundary_fields(
    declaration_sources: dict[str, str],
    consumer_sources: dict[str, str],
) -> list[tuple[str, str, str]]:
    """Find neutral dataclass fields with no receiver-bound production read.

    Constructor keywords and test-only references are intentionally not
    consumers. A same-named attribute on an unrelated object is not a
    consumer: the lightweight resolver follows annotations, constructor and
    function return types, assignments, imports, and nested dataclass fields.
    """
    declarations: list[tuple[str, str, str]] = []
    all_sources = {**declaration_sources, **consumer_sources}
    parsed_sources = {source_path: ast.parse(text, filename=source_path) for source_path, text in all_sources.items()}
    parsed_declarations = {source_path: parsed_sources[source_path] for source_path in declaration_sources}

    class_nodes: dict[str, list[tuple[str, ast.ClassDef]]] = {}
    for source_path, tree in parsed_sources.items():
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_nodes.setdefault(node.name, []).append((source_path, node))
    # Simple names are sufficient only when unambiguous. This intentionally
    # refuses to guess between unrelated same-named classes.
    known_fields: dict[str, dict[str, str | None]] = {
        name: {} for name, owners in class_nodes.items() if len(owners) == 1
    }
    class_paths: dict[str, str] = {}

    def annotation_type(node: ast.expr | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                return annotation_type(ast.parse(node.value, mode="eval").body)
            except SyntaxError:
                return None
        if isinstance(node, ast.Name):
            return node.id if node.id in known_fields else None
        if isinstance(node, ast.Attribute):
            return node.attr if node.attr in known_fields else None
        if isinstance(node, ast.Subscript):
            candidates = node.slice.elts if isinstance(node.slice, ast.Tuple) else (node.slice,)
            for candidate in reversed(candidates):
                if resolved := annotation_type(candidate):
                    return resolved
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return annotation_type(node.left) or annotation_type(node.right)
        return None

    # Register the reportable boundary classes. Other uniquely named classes
    # remain in ``known_fields`` solely to carry receiver types through nested
    # expressions such as ``context.preflight.video_info.has_audio``.
    for source_path, tree in parsed_declarations.items():
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and "dataclass" in {
                name for decorator in node.decorator_list if (name := _decorator_name(decorator)) is not None
            }:
                if node.name in class_paths:
                    raise ContractParseError(f"duplicate Python boundary class name: {node.name}")
                if node.name not in known_fields:
                    raise ContractParseError(f"ambiguous Python boundary class name: {node.name}")
                class_paths[node.name] = source_path

    for name, owners in class_nodes.items():
        if name not in known_fields:
            continue
        _source_path, node = owners[0]
        for member in node.body:
            if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                known_fields[name][member.target.id] = annotation_type(member.annotation)

    class_fields = {name: known_fields[name] for name in class_paths}

    for source_path, tree in parsed_declarations.items():
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name not in class_fields:
                continue
            for member in node.body:
                if not isinstance(member, ast.AnnAssign) or not isinstance(member.target, ast.Name):
                    continue
                if member.target.id.startswith("_"):
                    continue
                declarations.append((source_path, node.name, member.target.id))

    def module_name(source_path: str) -> str:
        normalized = source_path.replace("\\", "/")
        if normalized.startswith("backend/"):
            normalized = normalized.removeprefix("backend/")
        if normalized.endswith("/__init__.py"):
            return normalized.removesuffix("/__init__.py").replace("/", ".")
        return normalized.removesuffix(".py").replace("/", ".")

    module_exports: dict[str, dict[str, str]] = {}
    for source_path, tree in parsed_sources.items():
        exports = module_exports.setdefault(module_name(source_path), {})
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in known_fields:
                exports[node.name] = node.name
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if resolved := annotation_type(node.returns):
                    exports[node.name] = resolved
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if resolved := annotation_type(node.annotation):
                    exports[node.target.id] = resolved

    consumed: set[tuple[str, str]] = set()

    class BoundaryReadVisitor(ast.NodeVisitor):
        def __init__(self, source_path: str, tree: ast.Module) -> None:
            self.source_path = source_path
            self.tree = tree
            self.module = module_name(source_path)
            self.module_env = dict(module_exports.get(self.module, {}))
            self.scopes: list[dict[str, str]] = [self.module_env]
            self.class_stack: list[str | None] = []
            self._load_imports(tree)

        @property
        def env(self) -> dict[str, str]:
            return self.scopes[-1]

        def _load_imports(self, tree: ast.Module) -> None:
            for statement in tree.body:
                if not isinstance(statement, ast.ImportFrom) or not statement.module:
                    continue
                exports = module_exports.get(statement.module, {})
                for alias in statement.names:
                    if resolved := exports.get(alias.name):
                        self.module_env[alias.asname or alias.name] = resolved

        def _lookup(self, name: str) -> str | None:
            for scope in reversed(self.scopes):
                if name in scope:
                    return scope[name]
            return name if name in known_fields else None

        def _infer(self, node: ast.expr | None) -> str | None:
            if node is None:
                return None
            if isinstance(node, ast.Name):
                return self._lookup(node.id)
            if isinstance(node, ast.Attribute):
                owner = self._infer(node.value)
                if owner and node.attr in known_fields.get(owner, {}):
                    return known_fields[owner][node.attr]
                return None
            if isinstance(node, ast.Subscript):
                return self._infer(node.value)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    return self._lookup(node.func.id)
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "items", "values"}:
                    return self._infer(node.func.value)
                return None
            if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
                return next((resolved for item in node.elts if (resolved := self._infer(item))), None)
            if isinstance(node, ast.Dict):
                return next((resolved for item in node.values if (resolved := self._infer(item))), None)
            if isinstance(node, ast.IfExp):
                return self._infer(node.body) or self._infer(node.orelse)
            return None

        def _bind(self, target: ast.expr, resolved: str | None) -> None:
            if resolved is None:
                return
            if isinstance(target, ast.Name):
                self.env[target.id] = resolved
            elif isinstance(target, (ast.Tuple, ast.List)):
                for element in target.elts:
                    self._bind(element, resolved)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            owner = node.name if node.name in known_fields else None
            self.class_stack.append(owner)
            for statement in node.body:
                self.visit(statement)
            self.class_stack.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            local = dict(self.module_env)
            arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            for argument in arguments:
                if resolved := annotation_type(argument.annotation):
                    local[argument.arg] = resolved
            if self.class_stack and self.class_stack[-1] and arguments:
                local[arguments[0].arg] = self.class_stack[-1]
            self.scopes.append(local)
            for statement in node.body:
                self.visit(statement)
            self.scopes.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._visit_function(node)

        def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
            self.visit(node.value)
            resolved = self._infer(node.value)
            for target in node.targets:
                self._bind(target, resolved)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
            if node.value is not None:
                self.visit(node.value)
            self._bind(node.target, annotation_type(node.annotation) or self._infer(node.value))

        def visit_For(self, node: ast.For) -> None:  # noqa: N802
            self.visit(node.iter)
            self._bind(node.target, self._infer(node.iter))
            for statement in (*node.body, *node.orelse):
                self.visit(statement)

        def _visit_comprehension(
            self,
            generators: list[ast.comprehension],
            values: tuple[ast.expr, ...],
        ) -> None:
            self.scopes.append(dict(self.env))
            for generator in generators:
                self.visit(generator.iter)
                self._bind(generator.target, self._infer(generator.iter))
                for condition in generator.ifs:
                    self.visit(condition)
            for value in values:
                self.visit(value)
            self.scopes.pop()

        def visit_ListComp(self, node: ast.ListComp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.elt,))

        def visit_SetComp(self, node: ast.SetComp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.elt,))

        def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.elt,))

        def visit_DictComp(self, node: ast.DictComp) -> None:  # noqa: N802
            self._visit_comprehension(node.generators, (node.key, node.value))

        def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
            if isinstance(node.ctx, ast.Load):
                owner = self._infer(node.value)
                if owner and node.attr in class_fields.get(owner, {}):
                    consumed.add((owner, node.attr))
            self.generic_visit(node)

    for source_path, tree in parsed_sources.items():
        BoundaryReadVisitor(source_path, tree).visit(tree)

    return sorted(declaration for declaration in declarations if (declaration[1], declaration[2]) not in consumed)


def _check_python_boundary_field_consumers(root: Path) -> list[str]:
    declaration_paths = [
        *sorted((root / "backend/app/catalog").glob("*.py")),
        *sorted((root / "backend/app/ports").glob("*.py")),
    ]
    declaration_sources = {
        relative_path(path, root): read_source(path, root) for path in declaration_paths if path.name != "__init__.py"
    }
    app_root = root / "backend/app"
    consumer_sources = {
        relative_path(path, root): read_source(path, root)
        for path in sorted(app_root.rglob("*.py"))
        if "generated" not in path.parts and "vendor" not in path.parts and not path.name.startswith("ifnet_v4_")
    }
    return [
        f"Python boundary field has no production consumer: {source_path} -> {owner}.{field}"
        for source_path, owner, field in _find_unconsumed_python_boundary_fields(
            declaration_sources,
            consumer_sources,
        )
    ]


def _literal_all_names(tree: ast.Module) -> set[str]:
    for statement in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value
        if not isinstance(target, ast.Name) or target.id != "__all__" or value is None:
            continue
        try:
            names = ast.literal_eval(value)
        except (TypeError, ValueError) as exc:
            raise ContractParseError("Python package __all__ must be a literal sequence") from exc
        if not isinstance(names, (list, tuple)) or not all(isinstance(name, str) for name in names):
            raise ContractParseError("Python package __all__ must contain only literal names")
        if len(names) != len(set(names)):
            raise ContractParseError("Python package __all__ contains duplicate names")
        return set(names)
    return set()


@cache
def _parse_python_text(text: str) -> ast.Module:
    return ast.parse(text)


def _find_unconsumed_python_package_reexports(
    package_module: str,
    init_text: str,
    consumer_sources: list[str],
) -> set[str]:
    exported = _literal_all_names(ast.parse(init_text))
    consumed: set[str] = set()
    for text in consumer_sources:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != package_module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    consumed.update(exported)
                else:
                    consumed.add(alias.name)
    return exported - consumed


def _absolute_python_import_module(
    current_module: str,
    *,
    current_is_package: bool,
    imported_module: str | None,
    level: int,
) -> str:
    if level == 0:
        return imported_module or ""
    package = current_module if current_is_package else current_module.rpartition(".")[0]
    parts = package.split(".") if package else []
    ascend = level - 1
    if ascend > len(parts):
        return ""
    resolved = parts[: len(parts) - ascend]
    if imported_module:
        resolved.extend(imported_module.split("."))
    return ".".join(resolved)


def _dotted_python_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted_python_name(node.value)
        return f"{owner}.{node.attr}" if owner else None
    return None


def _find_unconsumed_python_module_exports(
    module_name: str,
    module_text: str,
    consumer_modules: list[tuple[str, bool, str]],
) -> set[str]:
    """Find ordinary-module exports with no external production consumer."""
    tree = _parse_python_text(module_text)
    exported = _literal_all_names(tree)
    if not exported:
        return set()

    # Internal reads prove that the symbol is live, not that it belongs to the
    # module's public surface. Only another production module can justify an
    # ordinary-module export.
    consumed: set[str] = set()

    for consumer_module, consumer_is_package, text in consumer_modules:
        consumer_tree = _parse_python_text(text)
        module_aliases: dict[str, str] = {}
        for node in ast.walk(consumer_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".")[0]
                    module_aliases[local_name] = alias.name if alias.asname else local_name
                continue
            if not isinstance(node, ast.ImportFrom):
                continue
            imported_from = _absolute_python_import_module(
                consumer_module,
                current_is_package=consumer_is_package,
                imported_module=node.module,
                level=node.level,
            )
            if imported_from == module_name:
                for alias in node.names:
                    if alias.name == "*":
                        consumed.update(exported)
                    elif alias.name in exported:
                        consumed.add(alias.name)
            for alias in node.names:
                candidate_module = f"{imported_from}.{alias.name}" if imported_from else alias.name
                if candidate_module == module_name:
                    module_aliases[alias.asname or alias.name] = module_name

        for node in ast.walk(consumer_tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
                continue
            dotted = _dotted_python_name(node)
            if not dotted:
                continue
            first, separator, remainder = dotted.partition(".")
            resolved = f"{module_aliases[first]}.{remainder}" if separator and first in module_aliases else dotted
            prefix = f"{module_name}."
            if resolved.startswith(prefix):
                exported_name = resolved[len(prefix) :].partition(".")[0]
                if exported_name in exported:
                    consumed.add(exported_name)

    return exported - consumed


def _check_python_package_reexports(root: Path) -> list[str]:
    app_root = root / "backend/app"
    production_paths = [
        path
        for path in sorted(app_root.rglob("*.py"))
        if "generated" not in path.parts and "vendor" not in path.parts and not path.name.startswith("ifnet_v4_")
    ]
    issues: list[str] = []
    for init_path in (path for path in production_paths if path.name == "__init__.py"):
        package_module = _python_module_name(app_root, init_path)
        consumers = [read_source(path, root) for path in production_paths if path != init_path]
        issues.extend(
            f"unconsumed Python package re-export `{name}`: {relative_path(init_path, root)}"
            for name in sorted(
                _find_unconsumed_python_package_reexports(
                    package_module,
                    read_source(init_path, root),
                    consumers,
                )
            )
        )
    return issues


def _check_python_module_exports(root: Path) -> list[str]:
    app_root = root / "backend/app"
    production_paths = [
        path
        for path in sorted(app_root.rglob("*.py"))
        if "generated" not in path.parts and "vendor" not in path.parts and not path.name.startswith("ifnet_v4_")
    ]
    module_sources = [
        (
            _python_module_name(app_root, path),
            path.name == "__init__.py",
            read_source(path, root),
            path,
        )
        for path in production_paths
    ]
    issues: list[str] = []
    for module_name, is_package, source, path in module_sources:
        if is_package:
            continue
        consumers = [
            (consumer_module, consumer_is_package, consumer_source)
            for consumer_module, consumer_is_package, consumer_source, consumer_path in module_sources
            if consumer_path != path
        ]
        issues.extend(
            f"Python module export has no production consumer: {relative_path(path, root)} -> {name}"
            for name in sorted(_find_unconsumed_python_module_exports(module_name, source, consumers))
        )
    return issues


def _python_module_name(app_root: Path, path: Path) -> str:
    parts = list(path.relative_to(app_root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_inert_package_statement(statement: ast.stmt, *, first: bool) -> bool:
    if first and isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return isinstance(statement.value.value, str)
    return isinstance(statement, ast.ImportFrom) and statement.module == "__future__"


def _check_side_effect_free_python_packages(root: Path) -> list[str]:
    paths = (
        "backend/app/__init__.py",
        "backend/app/algorithms/__init__.py",
        "backend/app/algorithms/paddle/__init__.py",
        "backend/app/algorithms/pytorch/__init__.py",
        "backend/app/cli/__init__.py",
        "backend/app/cli/commands/__init__.py",
        "backend/app/processing/__init__.py",
    )
    issues: list[str] = []
    for relative in paths:
        path = root / relative
        tree = _parse_python(path, root)
        for index, statement in enumerate(tree.body):
            if not _is_inert_package_statement(statement, first=index == 0):
                issues.append(
                    f"side-effect-free Python package executes top-level {statement.__class__.__name__}: "
                    f"{relative}:{statement.lineno}"
                )
    return issues


def _literal_handler_registry(tree: ast.Module) -> dict[str, tuple[str, str]]:
    return literal_string_pair_registry(tree, "_HANDLERS")


def _check_python_cli_commands(root: Path) -> list[str]:
    main_path = root / "backend/app/cli/main.py"
    parser_path = root / "backend/app/cli/parser.py"
    main_tree = _parse_python(main_path, root)
    parser_tree = _parse_python(parser_path, root)
    registry = _literal_handler_registry(main_tree)
    manifest = json.loads(read_source(root / "contracts/ipc-manifest.json", root))
    generated_command_constants = {
        "STAGE_WORKER_SUBCOMMAND": manifest["stageWorkerCommand"]["subcommand"],
    }
    parser_handlers: set[str] = set()
    parser_commands: set[str] = set()
    for node in ast.walk(parser_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "add_parser" and node.args:
            command = node.args[0]
            if isinstance(command, ast.Constant) and isinstance(command.value, str):
                parser_commands.add(command.value)
            elif isinstance(command, ast.Name) and command.id in generated_command_constants:
                parser_commands.add(generated_command_constants[command.id])
        if node.func.attr == "set_defaults":
            for keyword in node.keywords:
                if keyword.arg == "handler" and isinstance(keyword.value, ast.Constant):
                    if not isinstance(keyword.value.value, str):
                        raise ContractParseError("CLI parser handler identifiers must be literal strings")
                    parser_handlers.add(keyword.value.value)

    issues: list[str] = []
    registry_keys = set(registry)
    if parser_handlers != registry_keys:
        issues.append(
            "Python CLI handler registry drift: "
            f"only-in-parser={sorted(parser_handlers - registry_keys)}, "
            f"only-in-registry={sorted(registry_keys - parser_handlers)}"
        )
    normalized_handlers = {handler.replace("_", "-") for handler in parser_handlers}
    if normalized_handlers != parser_commands:
        issues.append(
            "Python CLI parser command reachability drift: "
            f"without-handler={sorted(parser_commands - normalized_handlers)}, "
            f"without-command={sorted(normalized_handlers - parser_commands)}"
        )

    command_root = root / "backend/app/cli/commands"
    implementations: set[tuple[str, str]] = set()
    for path in sorted(command_root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module = _python_module_name(root / "backend/app", path)
        tree = _parse_python(path, root)
        implementations.update(
            (module, statement.name)
            for statement in tree.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name.startswith("cmd_")
        )
    registered_targets = set(registry.values())
    if registered_targets != implementations:
        issues.append(
            "Python CLI command implementation reachability drift: "
            f"unregistered={sorted(implementations - registered_targets)}, "
            f"missing={sorted(registered_targets - implementations)}"
        )

    eager_command_imports = sorted(
        {
            imported
            for node in main_tree.body
            for imported in (
                ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                + ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            )
            if imported.startswith("app.cli.commands")
        }
    )
    if eager_command_imports:
        issues.append(f"Python CLI command modules must be imported lazily: {eager_command_imports}")

    backend_subcommands = {
        manifest["backendProcessCommand"]["subcommand"],
        *(entry["subcommand"] for entry in manifest["backendOneShotCommands"]),
        manifest["stageWorkerCommand"]["subcommand"],
    }
    if not backend_subcommands <= parser_commands:
        issues.append(
            f"IPC backend subcommands are unreachable from Python CLI: {sorted(backend_subcommands - parser_commands)}"
        )
    return issues


def _is_frontend_test(path: Path) -> bool:
    return path.name.endswith(".spec.ts") or "__tests__" in path.parts or "tests" in path.parts


def _check_frontend_test_layout(root: Path) -> list[str]:
    frontend_src = root / "frontend/src"
    issues: list[str] = []
    for path in sorted(frontend_src.rglob("*")):
        if path.is_file() and path.name.endswith(".spec.ts"):
            issues.append(f"frontend unit test outside tests/unit: {relative_path(path, root)}")
        elif path.is_dir() and path.name == "__tests__":
            issues.append(f"frontend __tests__ directory outside tests/unit: {relative_path(path, root)}")
    return issues


def _check_frontend_dependency_boundaries(root: Path) -> list[str]:
    frontend_src = root / "frontend/src"
    issues: list[str] = []
    generated_allowed = (frontend_src / "types/protocol", frontend_src / "types/generated")
    for path in sorted(frontend_src.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".vue"} or _is_frontend_test(path):
            continue
        text = read_source(path, root)
        if not any(allowed == path.parent or allowed in path.parents for allowed in generated_allowed):
            if "@/types/generated/" in text:
                issues.append(f"generated type deep import outside protocol layer: {relative_path(path, root)}")
            if "@/types/protocol/" in text:
                issues.append(f"protocol submodule import outside protocol layer: {relative_path(path, root)}")

    for relative_root in ("frontend/src/views", "frontend/src/components"):
        for path in sorted((root / relative_root).rglob("*")):
            if not path.is_file() or path.suffix not in {".ts", ".tsx", ".vue"} or _is_frontend_test(path):
                continue
            text = read_source(path, root)
            if any(marker in text for marker in ("@/lib/ipc", "@tauri-apps/api", "safeInvoke(")):
                issues.append(f"direct IPC access in UI/store layer: {relative_path(path, root)}")
    return issues


def _find_unconsumed_protocol_reexports(index_text: str, consumer_texts: list[str]) -> set[str]:
    reexports = set(
        re.findall(
            r"^\s*export\s+type\s*\{\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\}\s+from\b",
            index_text,
            re.MULTILINE,
        )
    )
    imported: set[str] = set()
    import_pattern = re.compile(
        r"import(?:\s+type)?\s*\{(?P<body>[^}]*)\}\s*from\s*['\"]"
        r"(?:@/types/protocol|(?:\.\./)+protocol|\./index)['\"]",
    )
    for text in consumer_texts:
        for match in import_pattern.finditer(text):
            for entry in _split_top_level_commas(match.group("body")):
                name = entry.strip().removeprefix("type ").split(" as ", 1)[0].strip()
                if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name):
                    imported.add(name)
    return reexports - imported


def _check_frontend_protocol_reexports(root: Path) -> list[str]:
    protocol_root = root / "frontend/src/types/protocol"
    protocol_paths = [protocol_root / name for name in ("index.ts", "events.ts", "errors.ts")]
    frontend_src = root / "frontend/src"
    consumer_texts = [
        read_source(path, root)
        for path in sorted(frontend_src.rglob("*"))
        if path.is_file()
        and path.suffix in {".ts", ".tsx", ".vue"}
        and path not in protocol_paths
        and "generated" not in path.parts
    ]
    issues: list[str] = []
    for path in protocol_paths:
        issues.extend(
            f"unconsumed frontend protocol re-export `{name}`: {relative_path(path, root)}"
            for name in sorted(_find_unconsumed_protocol_reexports(read_source(path, root), consumer_texts))
        )
    return issues


def _find_unconsumed_rust_model_reexports(model_mod_text: str, consumer_texts: list[str]) -> set[str]:
    reexports: set[str] = set()
    for match in re.finditer(
        r"pub(?:\(crate\))?\s+use\s+\w+::\{(?P<body>.*?)\};",
        model_mod_text,
        re.DOTALL,
    ):
        for entry in _split_top_level_commas(match.group("body")):
            name = entry.split(" as ", 1)[-1].strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                reexports.add(name)
    reexports.update(
        re.findall(
            r"pub(?:\(crate\))?\s+use\s+\w+::([A-Za-z_][A-Za-z0-9_]*)\s*;",
            model_mod_text,
        )
    )

    imported: set[str] = set()
    grouped_import = re.compile(
        r"use\s+(?:crate|vp_workbench_lib)::models::\{(?P<body>.*?)\};",
        re.DOTALL,
    )
    direct_import = re.compile(
        r"(?:crate|vp_workbench_lib)::models::([A-Z][A-Za-z0-9_]*)\b",
    )
    for text in consumer_texts:
        for match in grouped_import.finditer(text):
            for entry in _split_top_level_commas(match.group("body")):
                if "::" in entry:
                    continue
                name = entry.split(" as ", 1)[0].strip()
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    imported.add(name)
        imported.update(direct_import.findall(text))
    return reexports - imported


def _check_rust_model_reexports(root: Path) -> list[str]:
    model_root = root / "frontend/src-tauri/src/models"
    model_mod_path = model_root / "mod.rs"
    rust_root = root / "frontend/src-tauri/src"
    consumer_texts = [
        re.split(r"^\s*#\[cfg\(test\)\]", read_source(path, root), maxsplit=1, flags=re.MULTILINE)[0]
        for path in sorted(rust_root.rglob("*.rs"))
        if model_root not in path.parents
    ]
    return [
        f"unconsumed Rust models re-export `{name}`: frontend/src-tauri/src/models/mod.rs"
        for name in sorted(_find_unconsumed_rust_model_reexports(read_source(model_mod_path, root), consumer_texts))
    ]


def _find_unreferenced_css_classes(css_text: str, consumer_texts: list[str]) -> set[str]:
    classes = set(re.findall(r"\.([A-Za-z_-][A-Za-z0-9_-]*)", css_text))
    consumer_text = "\n".join(consumer_texts)
    return {
        class_name
        for class_name in classes
        if not re.search(rf"(?<![A-Za-z0-9_-]){re.escape(class_name)}(?![A-Za-z0-9_-])", consumer_text)
    }


def _find_unused_css_custom_properties(css_text: str, consumer_texts: list[str]) -> set[str]:
    properties = set(re.findall(r"(--[A-Za-z0-9_-]+)\s*:", css_text))
    consumers = "\n".join(consumer_texts)
    return {
        property_name
        for property_name in properties
        if not re.search(rf"var\(\s*{re.escape(property_name)}(?:\s*[,)]|\s+)", consumers)
    }


def _check_frontend_global_css_classes(root: Path) -> list[str]:
    css_path = root / "frontend/src/style.css"
    frontend_src = root / "frontend/src"
    consumers = [
        read_source(path, root)
        for path in sorted(frontend_src.rglob("*"))
        if path.is_file() and path.suffix in {".ts", ".tsx", ".vue"}
    ]
    issues = [
        f"unreferenced global CSS class `.{class_name}`: frontend/src/style.css"
        for class_name in sorted(_find_unreferenced_css_classes(read_source(css_path, root), consumers))
    ]
    issues.extend(
        f"unused global CSS custom property `{property_name}`: frontend/src/style.css"
        for property_name in sorted(
            _find_unused_css_custom_properties(read_source(css_path, root), [read_source(css_path, root), *consumers])
        )
    )
    return issues


def _find_unconsumed_test_ids(source_texts: list[str], test_texts: list[str]) -> set[str]:
    test_ids = {
        test_id for text in source_texts for test_id in re.findall(r"data-testid\s*=\s*['\"]([^'\"]+)['\"]", text)
    }
    tests = "\n".join(test_texts)
    return {test_id for test_id in test_ids if test_id not in tests}


def _check_frontend_test_ids(root: Path) -> list[str]:
    frontend_src = root / "frontend/src"
    frontend_tests = root / "frontend/tests"
    source_texts = [read_source(path, root) for path in sorted(frontend_src.rglob("*.vue"))]
    test_texts = [
        read_source(path, root)
        for path in sorted(frontend_tests.rglob("*"))
        if path.is_file() and path.suffix in {".ts", ".tsx", ".vue"}
    ]
    return [
        f"unconsumed frontend data-testid `{test_id}`"
        for test_id in sorted(_find_unconsumed_test_ids(source_texts, test_texts))
    ]


def _find_unconsumed_test_support_exports(sources: dict[str, str]) -> list[tuple[str, str]]:
    declaration = re.compile(
        r"^export\s+(?:declare\s+)?(?:async\s+)?"
        r"(?:interface|type|class|function|const|let|var|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        re.MULTILINE,
    )
    issues: list[tuple[str, str]] = []
    for source_path, text in sources.items():
        if source_path.endswith(".spec.ts"):
            continue
        for name in declaration.findall(text):
            pattern = re.compile(rf"\b{re.escape(name)}\b")
            if not any(pattern.search(other_text) for path, other_text in sources.items() if path != source_path):
                issues.append((source_path, name))
    return issues


def _check_frontend_test_support_exports(root: Path) -> list[str]:
    frontend_tests = root / "frontend/tests"
    sources = {relative_path(path, root): read_source(path, root) for path in sorted(frontend_tests.rglob("*.ts"))}
    return [
        f"unconsumed frontend test support export `{name}`: {source_path}"
        for source_path, name in _find_unconsumed_test_support_exports(sources)
    ]


def _check_typed_ndjson_error_emission(root: Path) -> list[str]:
    path = root / "backend/app/__main__.py"
    manual_error_envelopes = re.findall(r"[\"']type[\"']\s*:\s*[\"']error[\"']", read_source(path, root))
    if len(manual_error_envelopes) != 1:
        return [
            f"normal CLI failures must keep only the bootstrap manual error envelope in {relative_path(path, root)}"
        ]
    return []


def _find_dependency_cycles(edges: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Return canonical directed cycles for a module dependency graph."""

    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            cycle = path[path.index(node) :]
            rotations = [cycle[index:] + cycle[:index] for index in range(len(cycle))]
            cycles.add(min(rotations))
            return
        for target in edges.get(node, set()):
            visit(target, (*path, node))

    for package in edges:
        visit(package, ())
    return sorted(cycles)


def _check_backend_package_cycles(root: Path) -> list[str]:
    app_root = root / "backend/app"
    edges: dict[str, set[str]] = {}
    for path in sorted(app_root.rglob("*.py")):
        relative_parts = path.relative_to(app_root).parts
        if "vendor" in relative_parts or path.name.startswith("ifnet_v4_"):
            continue
        source = relative_parts[0].removesuffix(".py")
        tree = _parse_python(path, root)
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            imports = ([module] if module else []) + names
            for imported in imports:
                if not imported.startswith("app."):
                    continue
                target = imported.split(".", 2)[1]
                if target != source:
                    edges.setdefault(source, set()).add(target)

    return [
        f"backend package dependency cycle: {' -> '.join((*cycle, cycle[0]))}"
        for cycle in _find_dependency_cycles(edges)
    ]


def _check_rust_package_cycles(root: Path) -> list[str]:
    rust_root = root / "frontend/src-tauri/src"
    lib_text = read_source(rust_root / "lib.rs", root)
    package_names = set(
        re.findall(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*;",
            lib_text,
            re.MULTILINE,
        )
    )
    edges: dict[str, set[str]] = {}
    dependency = re.compile(r"\bcrate::([A-Za-z_][A-Za-z0-9_]*)\b")
    for path in sorted(rust_root.rglob("*.rs")):
        relative_parts = path.relative_to(rust_root).parts
        source = path.stem if len(relative_parts) == 1 else relative_parts[0]
        if source not in package_names:
            continue
        for target in dependency.findall(read_source(path, root)):
            if target in package_names and target != source:
                edges.setdefault(source, set()).add(target)
    return [
        f"Rust package dependency cycle: {' -> '.join((*cycle, cycle[0]))}" for cycle in _find_dependency_cycles(edges)
    ]


def _check_rust_submodule_cycles(root: Path, package: str) -> list[str]:
    package_root = root / "frontend/src-tauri/src" / package
    module_paths = {path.stem: path for path in sorted(package_root.glob("*.rs")) if path.name != "mod.rs"}
    module_names = set(module_paths)
    qualified = re.compile(rf"\bcrate::{re.escape(package)}::([A-Za-z_][A-Za-z0-9_]*)\b")
    relative = re.compile(r"\bsuper::([A-Za-z_][A-Za-z0-9_]*)\b")
    edges: dict[str, set[str]] = {}
    for source, path in module_paths.items():
        module_source = read_source(path, root)
        targets = set(qualified.findall(module_source)) | set(relative.findall(module_source))
        edges[source] = {target for target in targets if target in module_names and target != source}
    return [
        f"Rust {package} submodule dependency cycle: {' -> '.join((*cycle, cycle[0]))}"
        for cycle in _find_dependency_cycles(edges)
    ]


def _check_rust_task_adapter_boundaries(root: Path) -> list[str]:
    task_root = root / "frontend/src-tauri/src/tasks"
    tauri_reference = re.compile(r"(?:\buse\s+tauri(?:::|\s*\{)|#\s*\[\s*tauri::|\btauri::)")
    allowed = {"commands.rs", "ports.rs", "spawn.rs"}
    issues: list[str] = []
    for path in sorted(task_root.glob("*.rs")):
        if path.name in allowed:
            continue
        if tauri_reference.search(read_source(path, root)):
            issues.append(f"Rust task core imports Tauri outside the composition adapters: {relative_path(path, root)}")
    return issues


_RUST_MUST_USE_METHOD = re.compile(
    r"\.(emit|begin_reaping|seal_owned|finish_once|fail_cleanup_once|confirm_cleanup|"
    r"wait|wait_bounded|terminate_and_reap)\s*\("
)
_RUST_ROLLBACK_CALL = re.compile(r"\b([A-Za-z0-9_]*rollback[A-Za-z0-9_]*)\s*\(")


def _rust_production_source(text: str) -> str:
    """Drop the conventional trailing ``#[cfg(test)] mod tests`` block."""
    return re.split(
        r"^[ \t]*#\s*\[\s*cfg\s*\(\s*test\s*\)\s*\][ \t]*\r?\n[ \t]*mod\s+tests\s*\{",
        text,
        maxsplit=1,
        flags=re.MULTILINE,
    )[0]


def _ignored_rust_must_use_calls(text: str) -> list[tuple[int, str]]:
    """Find explicitly discarded lifecycle/process ownership outcomes."""
    issues: list[tuple[int, str]] = []
    matches = [*_RUST_MUST_USE_METHOD.finditer(text), *_RUST_ROLLBACK_CALL.finditer(text)]
    for match in sorted(matches, key=lambda item: item.start()):
        operation = match.group(1)
        if operation == "rollback_start":
            # This mutation deliberately returns unit; there is no ownership
            # or rollback error result for a caller to inspect.
            continue
        opening = match.end() - 1
        try:
            closing = _find_matching(text, opening, "(", ")")
        except ContractParseError:
            continue
        cursor = closing + 1
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if text.startswith(".await", cursor):
            cursor += len(".await")
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
        if cursor >= len(text) or text[cursor] != ";":
            continue

        statement_start = max(text.rfind(delimiter, 0, match.start()) for delimiter in ";{}") + 1
        prefix = text[statement_start : match.start()]
        binding = re.search(r"\blet\s+(?:mut\s+)?([_A-Za-z][A-Za-z0-9_]*)[^=]*=\s*", prefix)
        if binding is not None and not binding.group(1).startswith("_"):
            continue
        if re.search(r"\b(?:return|break)\b", prefix):
            continue
        issues.append((text.count("\n", 0, match.start()) + 1, operation))
    return issues


def _check_rust_lifecycle_result_handling(root: Path) -> list[str]:
    source_roots = (
        root / "frontend/src-tauri/src/tasks",
        root / "frontend/src-tauri/src/process_control",
    )
    issues: list[str] = []
    for source_root in source_roots:
        for path in sorted(source_root.glob("*.rs")):
            production = _rust_production_source(read_source(path, root))
            issues.extend(
                "Rust lifecycle/process result is explicitly ignored "
                f"(`{operation}`): {relative_path(path, root)}:{line}"
                for line, operation in _ignored_rust_must_use_calls(production)
            )
    return issues


def _rust_process_owner_helpers(sources: list[str]) -> set[str]:
    """Find wrappers that directly or transitively perform process-owner operations."""
    function_header = re.compile(
        r"\b(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)[^;{]*\{",
        re.MULTILINE,
    )
    process_owner_operation = re.compile(r"\b(?:terminate_and_reap|try_wait|start_kill|request_termination)\b")
    functions: list[tuple[str, str]] = []
    for source in sources:
        for match in function_header.finditer(source):
            opening = match.end() - 1
            try:
                closing = _find_matching(source, opening, "{", "}")
            except ContractParseError:
                continue
            functions.append((match.group(1), source[opening + 1 : closing]))

    hazardous = {name for name, body in functions if process_owner_operation.search(body)}
    changed = True
    while changed:
        changed = False
        call_pattern = re.compile(rf"\b(?:{'|'.join(map(re.escape, sorted(hazardous)))})\s*\(") if hazardous else None
        if call_pattern is None:
            break
        for name, body in functions:
            if name not in hazardous and call_pattern.search(body):
                hazardous.add(name)
                changed = True
    return hazardous


def _detached_process_owner_spawns(text: str, hazardous_helpers: set[str]) -> list[int]:
    spawn = re.compile(r"\b(?:tokio::spawn|tauri::async_runtime::spawn|runtime\.spawn)\s*\(")
    process_owner_operation = re.compile(r"\b(?:terminate_and_reap|try_wait|start_kill|request_termination)\b")
    helper_call = (
        re.compile(rf"\b(?:{'|'.join(map(re.escape, sorted(hazardous_helpers)))})\s*\(") if hazardous_helpers else None
    )
    lines: list[int] = []
    for match in spawn.finditer(text):
        opening = match.end() - 1
        try:
            closing = _find_matching(text, opening, "(", ")")
        except ContractParseError:
            continue
        statement_start = max(text.rfind(delimiter, 0, match.start()) for delimiter in ";{}") + 1
        prefix = text[statement_start : match.start()]
        binding = re.search(
            r"\blet\s+(?:mut\s+)?([A-Za-z_][A-Za-z0-9_]*)[^=]*=\s*$",
            prefix,
        )
        retained = (binding is not None and not binding.group(1).startswith("_")) or re.search(r"\breturn\s*$", prefix)
        body = text[opening + 1 : closing]
        if not retained and (
            process_owner_operation.search(body) or (helper_call is not None and helper_call.search(body))
        ):
            lines.append(text.count("\n", 0, match.start()) + 1)
    return lines


def _check_rust_reaper_ownership(root: Path) -> list[str]:
    """Keep detached process ownership inside the ticket-publishing adapter."""
    task_root = root / "frontend/src-tauri/src/tasks"
    issues: list[str] = []
    production_sources = {
        path: _rust_production_source(read_source(path, root))
        for path in sorted(task_root.glob("*.rs"))
        if path.name != "subprocess.rs"
    }
    hazardous_helpers = _rust_process_owner_helpers(list(production_sources.values()))
    for path, production in production_sources.items():
        issues.extend(
            "Rust process owner is reaped by a fire-and-forget task outside subprocess.rs: "
            f"{relative_path(path, root)}:{line}"
            for line in _detached_process_owner_spawns(production, hazardous_helpers)
        )

    adapter = task_root / "subprocess.rs"
    if adapter.is_file():
        adapter_source = _rust_production_source(read_source(adapter, root))
        required_markers = (
            "impl Drop for ProcessGroupOwner",
            "submit_cleanup(CleanupRequest::new(",
            "_worker: thread::JoinHandle<()>",
            "publish_once(&self.outcome, ReapOutcome::Reaped)",
            "publish_once(&self.outcome, ReapOutcome::Failed",
        )
        missing = [marker for marker in required_markers if marker not in adapter_source]
        if missing:
            issues.append(
                f"Rust cleanup coordinator does not retain ownership and publish every outcome: missing={missing}"
            )
    return issues


def _cargo_dependency_names_by_kind(cargo: dict[str, object]) -> dict[str, set[str]]:
    names = {section: set() for section in ("dependencies", "dev-dependencies", "build-dependencies")}

    def collect(section: str, table: object) -> None:
        if not isinstance(table, dict):
            return
        # Cargo source code refers to the dependency table key, including when
        # `package = "..."` renames the upstream package. Scanning the package
        # value would falsely report a used alias and miss the actual crate
        # identifier present in Rust source.
        names[section].update(str(dependency_name) for dependency_name in table)

    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        collect(section, cargo.get(section))
    targets = cargo.get("target")
    if isinstance(targets, dict):
        for target in targets.values():
            if not isinstance(target, dict):
                continue
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                collect(section, target.get(section))
    return names


def _schema_contains_pattern(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (key == "pattern" and isinstance(child, str)) or _schema_contains_pattern(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_schema_contains_pattern(child) for child in value)
    return False


def _is_typify_generated_dependency(
    *,
    root: Path,
    crate_root: Path,
    dependency_name: str,
    dependency_names: set[str],
    source_paths: list[Path],
) -> bool:
    """Recognize the one runtime crate emitted by Typify's pattern support."""
    if dependency_name != "regress" or "typify" not in dependency_names:
        return False
    macro = re.compile(r'typify::import_types!\s*\(\s*schema\s*=\s*"([^"]+)"\s*\)')
    contract_root = (root / "contracts").resolve()
    for path in source_paths:
        if not path.is_file():
            continue
        for schema_reference in macro.findall(read_source(path, root)):
            schema_path = (crate_root / schema_reference).resolve()
            if not schema_path.is_relative_to(contract_root):
                raise ContractParseError(
                    "Typify schema used to justify a generated dependency must live under contracts/: "
                    f"{relative_path(schema_path, root)}"
                )
            try:
                schema = json.loads(read_source(schema_path, root))
            except json.JSONDecodeError as exc:
                raise ContractParseError(f"invalid Typify JSON schema: {relative_path(schema_path, root)}") from exc
            if _schema_contains_pattern(schema):
                return True
    return False


def _check_rust_unused_dependencies(root: Path) -> list[str]:
    crate_root = root / "frontend/src-tauri"
    cargo_path = crate_root / "Cargo.toml"
    try:
        cargo = tomllib.loads(read_source(cargo_path, root))
    except tomllib.TOMLDecodeError as exc:
        raise ContractParseError(f"invalid Cargo.toml: {exc}") from exc

    production_paths = sorted((crate_root / "src").rglob("*.rs"))
    build_paths = [crate_root / "build.rs"]
    dev_paths = [*production_paths, *sorted((crate_root / "tests").rglob("*.rs"))]
    paths_by_kind = {
        "dependencies": production_paths,
        "build-dependencies": build_paths,
        "dev-dependencies": dev_paths,
    }
    dependency_names_by_kind = _cargo_dependency_names_by_kind(cargo)
    all_dependency_names = set().union(*dependency_names_by_kind.values())
    dependency_labels = {
        "dependencies": "dependency",
        "dev-dependencies": "dev-dependency",
        "build-dependencies": "build-dependency",
    }
    issues: list[str] = []
    for kind, dependency_names in dependency_names_by_kind.items():
        source_paths = paths_by_kind[kind]
        source = "\n".join(read_source(path, root) for path in source_paths if path.is_file())
        for dependency_name in sorted(dependency_names):
            crate_name = dependency_name.replace("-", "_")
            if re.search(rf"\b{re.escape(crate_name)}\b", source) is None and not _is_typify_generated_dependency(
                root=root,
                crate_root=crate_root,
                dependency_name=dependency_name,
                dependency_names=all_dependency_names,
                source_paths=source_paths,
            ):
                issues.append(
                    f"unused Rust Cargo {dependency_labels[kind]} `{dependency_name}`: frontend/src-tauri/Cargo.toml"
                )
    return issues


_RUST_PUBLIC_API_FILES = (
    "frontend/src-tauri/src/lib.rs",
    "frontend/src-tauri/src/models/mod.rs",
)

_RUST_PUBLIC_MODEL_EXPORTS = {
    "config": frozenset(
        {
            "DecodeConfig",
            "DecodeMode",
            "EncodeConfig",
            "FilterStep",
            "FilterStepKind",
            "FpsMode",
            "InferenceEngine",
            "InterpolationConfig",
            "OutputConfig",
            "PostprocessConfig",
            "PreprocessConfig",
            "ProcessOrder",
            "RateControlConfig",
            "RateControlMode",
            "SuperResolutionConfig",
            "TensorBackend",
            "WorkbenchPreset",
            "WorkflowConfig",
        }
    ),
    "task": frozenset(
        {
            "ResumeInspectionEventType",
            "ResumeInspectionResult",
            "ResumeMode",
            "ResumePipelineKind",
            "ResumeStatusPayload",
            "TaskCancelledPayload",
            "TaskCancelledReason",
            "TaskCompletedPayload",
            "TaskErrorPayload",
            "TaskLogPayload",
            "TaskProgressPayload",
            "TaskRequest",
            "VideoInfo",
        }
    ),
}


def _rust_public_declarations(text: str) -> list[tuple[int, str]]:
    declarations: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if re.match(r"^pub\s+(?!\()", stripped):
            declarations.append((line_number, stripped))
    return declarations


def _check_rust_public_surface(root: Path) -> list[str]:
    rust_root = root / "frontend/src-tauri/src"
    api_paths = {relative: root / relative for relative in _RUST_PUBLIC_API_FILES}
    issues = [
        f"Rust public API allowlist path does not exist: {relative}"
        for relative, path in api_paths.items()
        if not path.is_file()
    ]

    for path in sorted(rust_root.rglob("*.rs")) if rust_root.is_dir() else ():
        relative = relative_path(path, root)
        if relative in api_paths:
            continue
        if _rust_public_declarations(_rust_production_source(read_source(path, root))):
            issues.append(f"Rust crate-internal source exposes a public item: {relative}")

    lib_path = api_paths[_RUST_PUBLIC_API_FILES[0]]
    if lib_path.is_file():
        declarations = _rust_public_declarations(_rust_production_source(read_source(lib_path, root)))
        expected = {"pub mod models;", "pub fn run() {"}
        actual = {declaration for _, declaration in declarations}
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing or unexpected:
            issues.append(f"Rust crate public API drifted: missing={missing}, unexpected={unexpected}")

    models_path = api_paths[_RUST_PUBLIC_API_FILES[1]]
    if models_path.is_file():
        source = _rust_production_source(read_source(models_path, root))
        module_pattern = re.compile(r"^pub mod ([A-Za-z_][A-Za-z0-9_]*)\s*\{", re.MULTILINE)
        modules: dict[str, str] = {}
        for match in module_pattern.finditer(source):
            opening = source.find("{", match.start(), match.end())
            closing = _find_matching(source, opening, "{", "}")
            modules[match.group(1)] = source[opening + 1 : closing]

        expected_modules = set(_RUST_PUBLIC_MODEL_EXPORTS)
        actual_modules = set(modules)
        missing_modules = sorted(expected_modules - actual_modules)
        unexpected_modules = sorted(actual_modules - expected_modules)
        if missing_modules or unexpected_modules:
            issues.append(
                f"Rust models public modules drifted: missing={missing_modules}, unexpected={unexpected_modules}"
            )

        for module, expected_exports in _RUST_PUBLIC_MODEL_EXPORTS.items():
            body = modules.get(module)
            if body is None:
                continue
            reexports = re.findall(r"pub use super::boundary::\{(.*?)\};", body, re.DOTALL)
            if len(reexports) != 1:
                issues.append(f"Rust models `{module}` must contain exactly one generated boundary re-export")
                continue
            actual_exports = {item.strip() for item in reexports[0].split(",") if item.strip()}
            missing_exports = sorted(expected_exports - actual_exports)
            unexpected_exports = sorted(actual_exports - expected_exports)
            if missing_exports or unexpected_exports:
                issues.append(
                    f"Rust models `{module}` public schema drifted: "
                    f"missing={missing_exports}, unexpected={unexpected_exports}"
                )

        allowed_declarations = {
            *(f"pub mod {module} {{" for module in _RUST_PUBLIC_MODEL_EXPORTS),
            "pub use super::boundary::{",
        }
        unexpected_declarations = [
            f"{line}: {declaration}"
            for line, declaration in _rust_public_declarations(source)
            if declaration not in allowed_declarations
        ]
        if unexpected_declarations:
            issues.append(f"Rust models expose non-schema public items: {unexpected_declarations}")

    return issues


def collect_architecture_issues(root: Path) -> list[str]:
    issues = run_rules(root, RULES)
    issues.extend(_check_command_surface(root))
    issues.extend(_check_paddlegan_metadata(root))
    issues.extend(_check_python_algorithm_factory_registry(root))
    issues.extend(_check_python_cli_commands(root))
    issues.extend(_check_side_effect_free_python_packages(root))
    issues.extend(_check_python_boundary_field_consumers(root))
    issues.extend(_check_python_package_reexports(root))
    issues.extend(_check_python_module_exports(root))
    issues.extend(_check_frontend_test_layout(root))
    issues.extend(_check_frontend_dependency_boundaries(root))
    issues.extend(_check_frontend_protocol_reexports(root))
    issues.extend(_check_rust_model_reexports(root))
    issues.extend(_check_frontend_global_css_classes(root))
    issues.extend(_check_frontend_test_ids(root))
    issues.extend(_check_frontend_test_support_exports(root))
    issues.extend(_check_typed_ndjson_error_emission(root))
    issues.extend(_check_backend_package_cycles(root))
    issues.extend(_check_rust_package_cycles(root))
    issues.extend(_check_rust_submodule_cycles(root, "tasks"))
    issues.extend(_check_rust_task_adapter_boundaries(root))
    issues.extend(_check_rust_lifecycle_result_handling(root))
    issues.extend(_check_rust_reaper_ownership(root))
    issues.extend(_check_rust_unused_dependencies(root))
    issues.extend(_check_rust_public_surface(root))
    return issues
