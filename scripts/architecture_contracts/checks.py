"""Semantic architecture checks that cannot be expressed as text rules."""

from __future__ import annotations

import ast
import contextlib
import io
import re
import sys
from pathlib import Path

from .catalog import RULES
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


def _collect_manifest_commands(root: Path) -> set[str]:
    path = root / "frontend/src-tauri/src/commands_manifest.rs"
    text = read_source(path, root)
    match = re.search(r"APP_COMMAND_NAMES:\s*&\[&str\]\s*=\s*&\[(?P<body>.*?)\];", text, re.DOTALL)
    if not match:
        raise ContractParseError("could not parse APP_COMMAND_NAMES in commands_manifest.rs")
    return set(re.findall(r'"([a-z_]+)"', match.group("body")))


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


def _collect_rust_command_args(root: Path) -> dict[str, set[str]]:
    tauri_src = root / "frontend/src-tauri/src"
    command_args: dict[str, set[str]] = {}
    command_attr = re.compile(r"^\s*#\s*\[\s*tauri::command\s*\]", re.MULTILINE)
    function_decl = re.compile(r"(?:#\[[^\]]+\]\s*)*pub\s+(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)")

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
            args: set[str] = set()
            for parameter in _split_top_level_commas(text[args_start + 1 : args_end]):
                if ":" not in parameter:
                    continue
                raw_name, raw_type = parameter.split(":", 1)
                type_name = raw_type.strip()
                if type_name.startswith(("AppHandle", "State<", "tauri::AppHandle", "tauri::State<")):
                    continue
                name = raw_name.strip().removeprefix("mut ").strip()
                args.add(_snake_to_camel(name) if "_" in name else name)
            command_args[command] = args
    return command_args


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


def _check_command_surface(root: Path) -> list[str]:
    manifest = _collect_manifest_commands(root)
    permissions = _collect_permission_commands(root)
    rust_args = _collect_rust_command_args(root)
    invoke_commands = _collect_frontend_invoke_commands(root)
    contract_args = _collect_typed_ipc_contract_args(root)
    issues = diff_command_surface(
        manifest=manifest,
        permissions=permissions,
        rust_args=rust_args,
        invoke_args=invoke_commands,
        contract_args=contract_args,
    )

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
    assignment = text.find(symbol)
    if assignment < 0:
        raise ContractParseError(f"could not find {symbol!r}")
    body_start = text.find("{", assignment)
    if body_start < 0:
        raise ContractParseError(f"could not find dict body for {symbol!r}")
    body_end = _find_matching(text, body_start, "{", "}")
    return set(re.findall(r"['\"]([a-z0-9-]+)['\"]\s*:", text[body_start + 1 : body_end]))


def _collect_backend_algorithm_metadata(root: Path) -> dict[str, dict[str, object]]:
    backend_dir = root / "backend"
    inserted = False
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
        inserted = True
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from app.processing.super_resolution import SUPPORTED_ALGORITHMS

        return {
            str(entry["name"]): {
                "family": entry.get("family"),
                "fixedScaleFactor": entry.get("fixedScaleFactor"),
                "inputFrameMode": entry.get("inputFrameMode"),
            }
            for entry in SUPPORTED_ALGORITHMS
        }
    finally:
        if inserted:
            sys.path.remove(str(backend_dir))


def diff_paddlegan_vsr_contract(backend_specs: set[str], algorithm_metadata: dict[str, dict[str, object]]) -> list[str]:
    issues: list[str] = []
    metadata_models = {
        name for name, metadata in algorithm_metadata.items() if metadata.get("family") == "paddlegan_vsr"
    }
    missing_metadata = backend_specs - metadata_models
    extra_metadata = metadata_models - backend_specs
    if missing_metadata or extra_metadata:
        issues.append(
            "PaddleGAN VSR metadata drift: "
            f"missing-metadata={sorted(missing_metadata)}, extra-metadata={sorted(extra_metadata)}"
        )
    for model_id in sorted(backend_specs & metadata_models):
        metadata = algorithm_metadata[model_id]
        if metadata.get("fixedScaleFactor") != 4:
            issues.append(f"PaddleGAN VSR `{model_id}` must expose fixedScaleFactor=4")
        expected_mode = "fixed_window" if model_id == "edvr" else "editable_chunk"
        if metadata.get("inputFrameMode") != expected_mode:
            issues.append(f"PaddleGAN VSR `{model_id}` must expose inputFrameMode={expected_mode!r}")
    return issues


def _check_paddlegan_metadata(root: Path) -> list[str]:
    weights = root / "backend/app/algorithms/paddle/paddlegan_vsr/weights.py"
    specs = _collect_python_dict_keys(read_source(weights, root), "PADDLEGAN_VSR_SPECS")
    return diff_paddlegan_vsr_contract(specs, _collect_backend_algorithm_metadata(root))


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

    for relative_root in ("frontend/src/views", "frontend/src/components", "frontend/src/stores"):
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
        r"import(?:\s+type)?\s*\{(?P<body>.*?)\}\s*from\s*['\"]"
        r"(?:@/types/protocol|(?:\.\./)+protocol|\./index)['\"]",
        re.DOTALL,
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


def _check_stage_sequence_metrics(root: Path) -> list[str]:
    execution_path = root / "backend/app/processing/streaming/stage_worker_execution.py"
    execution_tree = _parse_python(execution_path, root)
    issues: list[str] = []
    for node in ast.walk(execution_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "run_sequence_stage":
            continue
        parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if any(parameter.arg == "metrics" for parameter in parameters):
            issues.append(f"stage worker sequence metrics parameter remains in {relative_path(execution_path, root)}")
        if any(
            isinstance(child, ast.Delete)
            and any(isinstance(target, ast.Name) and target.id == "metrics" for target in child.targets)
            for child in ast.walk(node)
        ):
            issues.append(f"stage worker sequence metrics discard remains in {relative_path(execution_path, root)}")

    worker_path = root / "backend/app/processing/streaming/stage_worker.py"
    worker_tree = _parse_python(worker_path, root)
    for node in ast.walk(worker_tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "run_sequence_stage"
        ):
            continue
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        if any(isinstance(value, ast.Name) and value.id == "metrics" for value in values):
            issues.append(f"stage worker sequence metrics forwarding remains in {relative_path(worker_path, root)}")
    return issues


def collect_architecture_issues(root: Path) -> list[str]:
    issues = run_rules(root, RULES)
    issues.extend(_check_command_surface(root))
    issues.extend(_check_paddlegan_metadata(root))
    issues.extend(_check_frontend_test_layout(root))
    issues.extend(_check_frontend_dependency_boundaries(root))
    issues.extend(_check_frontend_protocol_reexports(root))
    issues.extend(_check_rust_model_reexports(root))
    issues.extend(_check_frontend_global_css_classes(root))
    issues.extend(_check_frontend_test_ids(root))
    issues.extend(_check_frontend_test_support_exports(root))
    issues.extend(_check_typed_ndjson_error_emission(root))
    issues.extend(_check_stage_sequence_metrics(root))
    return issues
