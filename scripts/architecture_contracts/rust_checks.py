"""Rust module, lifecycle, dependency, and public-surface checks."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .graph_ast import _find_dependency_cycles, _find_matching, _split_top_level_commas
from .rules import ContractParseError, read_source, relative_path
from .rust_source import production_rust_source


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
        production_rust_source(read_source(path, root))
        for path in sorted(rust_root.rglob("*.rs"))
        if model_root not in path.parents
    ]
    return [
        f"unconsumed Rust models re-export `{name}`: frontend/src-tauri/src/models/mod.rs"
        for name in sorted(_find_unconsumed_rust_model_reexports(read_source(model_mod_path, root), consumer_texts))
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
    allowed = {"commands.rs", "spawn.rs", "tauri_ports.rs"}
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
            production = production_rust_source(read_source(path, root))
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
        path: production_rust_source(read_source(path, root))
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
        adapter_source = production_rust_source(read_source(adapter, root))
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
        if _rust_public_declarations(production_rust_source(read_source(path, root))):
            issues.append(f"Rust crate-internal source exposes a public item: {relative}")

    lib_path = api_paths[_RUST_PUBLIC_API_FILES[0]]
    if lib_path.is_file():
        declarations = _rust_public_declarations(production_rust_source(read_source(lib_path, root)))
        expected = {"pub mod models;", "pub fn run() {"}
        actual = {declaration for _, declaration in declarations}
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing or unexpected:
            issues.append(f"Rust crate public API drifted: missing={missing}, unexpected={unexpected}")

    models_path = api_paths[_RUST_PUBLIC_API_FILES[1]]
    if models_path.is_file():
        source = production_rust_source(read_source(models_path, root))
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
