#!/usr/bin/env python3
"""Run production-only and full-suite Vulture gates."""

from __future__ import annotations

import ast
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

from vulture import Vulture
from vulture.core import Item

from architecture_contracts.python_ast import literal_string_pair_registry

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class ReviewedExclusion:
    path: str
    reason: str
    evidence_file: str
    evidence_marker: str
    protects_reachability: bool = True


@dataclass(frozen=True, slots=True)
class ReviewedSymbol:
    """One exact dynamically consumed symbol that Vulture cannot resolve."""

    path: str
    symbol: str
    reason: str
    evidence_file: str
    evidence_marker: str


_RIFE_CATALOG = ROOT / "backend/app/catalog/rife_models.py"
_RIFE_PACKAGE = ROOT / "backend/app/algorithms/pytorch/rife"


def _read_rife_catalog_versions(catalog_path: Path = _RIFE_CATALOG) -> tuple[str, ...]:
    """Statically read the neutral catalog without importing backend runtime code."""
    tree = ast.parse(catalog_path.read_text(encoding="utf-8"), filename=str(catalog_path))
    groups: ast.expr | None = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_VERSION_GROUPS":
                groups = node.value
                break
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_VERSION_GROUPS" for target in node.targets
        ):
            groups = node.value
            break
    if not isinstance(groups, (ast.List, ast.Tuple)):
        raise RuntimeError("RIFE neutral catalog must define a literal _VERSION_GROUPS sequence")

    versions: list[str] = []
    for group in groups.elts:
        if not isinstance(group, ast.Tuple) or not group.elts:
            raise RuntimeError("RIFE neutral catalog contains a non-tuple version group")
        version_node = group.elts[0]
        try:
            group_versions = ast.literal_eval(version_node)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("RIFE neutral catalog version groups must be literal sequences") from exc
        if not isinstance(group_versions, (list, tuple)) or not all(
            isinstance(version, str) for version in group_versions
        ):
            raise RuntimeError("RIFE neutral catalog contains an invalid version sequence")
        versions.extend(group_versions)

    if not versions or len(versions) != len(set(versions)):
        raise RuntimeError("RIFE neutral catalog versions must be non-empty and unique")
    return tuple(versions)


def _rife_module_paths(catalog_path: Path = _RIFE_CATALOG) -> tuple[str, ...]:
    return tuple(
        f"backend/app/algorithms/pytorch/rife/ifnet_v{version.replace('.', '_')}.py"
        for version in _read_rife_catalog_versions(catalog_path)
    )


_STATIC_REVIEWED_EXCLUSIONS = (
    ReviewedExclusion(
        path="backend/app/generated/contracts.py",
        reason="Generated Pydantic bindings are protected by byte-for-byte contract freshness.",
        evidence_file="backend/tests/test_contract_source_generation.py",
        evidence_marker="_render_boundary_schema",
    ),
    ReviewedExclusion(
        path="backend/app/generated/protocol_constants.py",
        reason="Generated protocol constants are protected by byte-for-byte contract freshness.",
        evidence_file="backend/tests/test_contract_source_generation.py",
        evidence_marker="_render_python_protocol_constants",
    ),
    ReviewedExclusion(
        path="backend/app/generated/stage_worker_contracts.py",
        reason="Generated stage-worker bindings are protected by byte-for-byte contract freshness.",
        evidence_file="backend/tests/test_contract_source_generation.py",
        evidence_marker="_render_stage_worker_schema",
        protects_reachability=False,
    ),
    ReviewedExclusion(
        path="backend/app/algorithms/paddle/paddlegan_vsr/vendor/",
        reason="Vendored PaddleGAN framework callbacks are reached dynamically by Paddle.",
        evidence_file="backend/tests/test_algorithms/test_paddlegan_vsr_specs.py",
        evidence_marker="test_vendor_auxiliary_weight_helper_uses_only_local_auxiliary_files",
    ),
)

_RIFE_REVIEWED_EXCLUSIONS = tuple(
    ReviewedExclusion(
        path=path,
        reason="RIFE model module is selected dynamically from the neutral version catalog.",
        evidence_file="backend/tests/test_algorithms/test_rife_all_models.py",
        evidence_marker="importlib.import_module(rife_package)",
    )
    for path in _rife_module_paths()
)

_REVIEWED_EXCLUSIONS = (*_STATIC_REVIEWED_EXCLUSIONS, *_RIFE_REVIEWED_EXCLUSIONS)

_PRODUCTION_REVIEWED_SYMBOLS = (
    ReviewedSymbol(
        path="backend/app/algorithms/pytorch/rife/onnx_export.py",
        symbol="forward",
        reason="PyTorch invokes the module forward method while tracing the ONNX export wrapper.",
        evidence_file="backend/tests/test_algorithms/test_rife_onnx.py",
        evidence_marker="class TestRIFEONNXExport",
    ),
    ReviewedSymbol(
        path="backend/app/algorithms/pytorch/rife/warplayer.py",
        symbol="warp",
        reason="The protected catalog-selected RIFE modules import and call this shared warp function.",
        evidence_file="backend/tests/test_algorithms/test_rife_all_models.py",
        evidence_marker="importlib.import_module(rife_package)",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/benchmark.py",
        symbol="cmd_benchmark",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_benchmark",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/check.py",
        symbol="cmd_check",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_check",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/info.py",
        symbol="cmd_info",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_info",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/inspect_output.py",
        symbol="cmd_inspect_output",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_inspect_output",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/process.py",
        symbol="cmd_process",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_process",
    ),
    ReviewedSymbol(
        path="backend/app/cli/commands/stage_worker.py",
        symbol="cmd_stage_worker",
        reason="The CLI composition root loads this command through its literal lazy-handler registry.",
        evidence_file="backend/app/cli/main.py",
        evidence_marker="cmd_stage_worker",
    ),
    ReviewedSymbol(
        path="backend/app/config.py",
        symbol="model_config",
        reason="Pydantic Settings reads this declarative class configuration during model construction.",
        evidence_file="backend/tests/test_config.py",
        evidence_marker="def _build_settings",
    ),
    ReviewedSymbol(
        path="backend/app/config.py",
        symbol="model_post_init",
        reason="Pydantic calls this lifecycle hook after validating each settings instance.",
        evidence_file="backend/tests/test_config.py",
        evidence_marker="def _build_settings",
    ),
    ReviewedSymbol(
        path="backend/app/config.py",
        symbol="__context",
        reason="Pydantic supplies this lifecycle-hook argument when it invokes model_post_init.",
        evidence_file="backend/tests/test_config.py",
        evidence_marker="def _build_settings",
    ),
    *(
        ReviewedSymbol(
            path="backend/app/processing/anime_cleanup.py",
            symbol=symbol,
            reason="This TypedDict field is consumed through keyed profile lookups in the frame filter.",
            evidence_file="backend/tests/test_processing/test_anime_cleanup.py",
            evidence_marker="def test_missing_strengths_use_profile_defaults",
        )
        for symbol in (
            "default_denoise",
            "default_edge_boost",
            "median_size",
            "denoise_gain",
            "edge_radius",
            "edge_gain",
            "edge_threshold",
        )
    ),
)

_FULL_SCAN_ONLY_REVIEWED_SYMBOLS = (
    ReviewedSymbol(
        path="backend/tests/conftest.py",
        symbol="collect_ignore",
        reason="Pytest reads collect_ignore while collecting backend-specific test files.",
        evidence_file="backend/tests/conftest.py",
        evidence_marker="collect_ignore =",
    ),
    *(
        ReviewedSymbol(
            path=path,
            symbol="pytestmark",
            reason="Pytest reads this module marker during collection.",
            evidence_file=path,
            evidence_marker="pytestmark =",
        )
        for path in (
            "backend/tests/test_algorithms/test_interpolation.py",
            "backend/tests/test_algorithms/test_rife_all_models.py",
            "backend/tests/test_algorithms/test_rife_onnx.py",
            "backend/tests/test_algorithms/test_rife_tensorrt.py",
            "backend/tests/test_algorithms/test_tensor_backend_pytorch.py",
            "backend/tests/test_weight_loading.py",
        )
    ),
    ReviewedSymbol(
        path="backend/tests/test_algorithms/test_rife_tensorrt.py",
        symbol="__spec__",
        reason="Importlib reads the synthetic module spec while probing the optional TensorRT module.",
        evidence_file="backend/tests/test_algorithms/test_rife_tensorrt.py",
        evidence_marker="fake_torch_tensorrt.__spec__ =",
    ),
    ReviewedSymbol(
        path="backend/tests/test_integration/test_cli_process_e2e.py",
        symbol="_cleanup_output",
        reason="Pytest invokes this autouse fixture without a static call site.",
        evidence_file="backend/tests/test_integration/test_cli_process_e2e.py",
        evidence_marker="@pytest.fixture(autouse=True)",
    ),
    ReviewedSymbol(
        path="backend/tests/test_logger.py",
        symbol="restore_root_logger",
        reason="Pytest invokes this autouse fixture without a static call site.",
        evidence_file="backend/tests/test_logger.py",
        evidence_marker="@pytest.fixture(autouse=True)",
    ),
    ReviewedSymbol(
        path="backend/tests/test_utils/test_dll_paths.py",
        symbol="_reset_registry",
        reason="Pytest invokes this autouse fixture without a static call site.",
        evidence_file="backend/tests/test_utils/test_dll_paths.py",
        evidence_marker="@pytest.fixture(autouse=True)",
    ),
    *(
        ReviewedSymbol(
            path="scripts/architecture_contracts/checks.py",
            symbol=symbol,
            reason="ast.NodeVisitor dispatches this visitor method by node type.",
            evidence_file="scripts/architecture_contracts/checks.py",
            evidence_marker="class BoundaryReadVisitor(ast.NodeVisitor)",
        )
        for symbol in (
            "visit_AnnAssign",
            "visit_Assign",
            "visit_AsyncFunctionDef",
            "visit_Attribute",
            "visit_ClassDef",
            "visit_DictComp",
            "visit_For",
            "visit_FunctionDef",
            "visit_GeneratorExp",
            "visit_ListComp",
            "visit_SetComp",
        )
    ),
)


def _validate_reviewed_exclusions() -> None:
    paths = [entry.path for entry in _REVIEWED_EXCLUSIONS]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate Python dead-code exclusion")
    for entry in _REVIEWED_EXCLUSIONS:
        if not entry.reason.strip():
            raise RuntimeError(f"missing reason for Python dead-code exclusion {entry.path}")
        protected = ROOT / entry.path.rstrip("/")
        if entry.path.endswith("/"):
            exists = protected.is_dir()
        else:
            exists = protected.is_file()
        if not exists:
            raise RuntimeError(f"Python dead-code exclusion does not match a protected path: {entry.path}")
        evidence = ROOT / entry.evidence_file
        if not evidence.is_file() or entry.evidence_marker not in evidence.read_text(encoding="utf-8"):
            raise RuntimeError(
                f"Python dead-code exclusion evidence is missing for {entry.path}: "
                f"{entry.evidence_file}::{entry.evidence_marker}"
            )

    expected_rife = {ROOT / path for path in _rife_module_paths()}
    actual_rife = set(_RIFE_PACKAGE.glob("ifnet_v4_*.py"))
    if actual_rife != expected_rife:
        missing = sorted(path.name for path in expected_rife - actual_rife)
        unexpected = sorted(path.name for path in actual_rife - expected_rife)
        raise RuntimeError(
            f"RIFE dynamic-module boundary drifted from the neutral catalog: missing={missing}, unexpected={unexpected}"
        )


def _declared_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.arg):
            symbols.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            symbols.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            symbols.add(node.attr)
    return symbols


def _validate_reviewed_symbols() -> None:
    entries = (*_PRODUCTION_REVIEWED_SYMBOLS, *_FULL_SCAN_ONLY_REVIEWED_SYMBOLS)
    keys = [(entry.path, entry.symbol) for entry in entries]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate path/symbol Python dead-code review")

    declared_by_path: dict[str, set[str]] = {}
    for entry in entries:
        if not entry.reason.strip():
            raise RuntimeError(f"missing reason for Python dead-code symbol {entry.path}::{entry.symbol}")
        source = ROOT / entry.path
        if not source.is_file():
            raise RuntimeError(f"Python dead-code symbol path does not exist: {entry.path}")
        if entry.path not in declared_by_path:
            declared_by_path[entry.path] = _declared_symbols(source)
        symbols = declared_by_path[entry.path]
        if entry.symbol not in symbols:
            raise RuntimeError(f"reviewed Python dead-code symbol is not declared: {entry.path}::{entry.symbol}")
        evidence = ROOT / entry.evidence_file
        if not evidence.is_file() or entry.evidence_marker not in evidence.read_text(encoding="utf-8"):
            raise RuntimeError(
                f"Python dead-code symbol evidence is missing for {entry.path}::{entry.symbol}: "
                f"{entry.evidence_file}::{entry.evidence_marker}"
            )


def _module_name(app_root: Path, path: Path) -> str:
    relative = path.relative_to(app_root.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_imports(
    *,
    module_name: str,
    path: Path,
    known_modules: set[str],
) -> set[str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    current_package = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]

    def include(module: str) -> None:
        parts = module.split(".")
        for length in range(1, len(parts) + 1):
            candidate = ".".join(parts[:length])
            if candidate in known_modules:
                imports.add(candidate)

    def include_lazy_handler_registry() -> None:
        """Add exact module edges declared by the CLI's immutable handler map.

        Lazy command loading intentionally stores module names as strings, so
        ordinary ``Import`` nodes cannot make those production modules
        reachable. Only the top-level ``_HANDLERS`` mapping is recognized;
        unrelated strings must never become reachability roots.
        """
        if module_name != "app.cli.main":
            return
        for registered_module, _ in _literal_handler_targets(path):
            if registered_module not in known_modules:
                raise RuntimeError(f"_HANDLERS references unknown production module: {registered_module}")
            include(registered_module)

    include_lazy_handler_registry()

    for node in _reachable_import_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app" or alias.name.startswith("app."):
                    include(alias.name)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            package_parts = current_package.split(".") if current_package else []
            ascend = node.level - 1
            if ascend >= len(package_parts):
                continue
            base_parts = package_parts[: len(package_parts) - ascend]
            if node.module:
                base_parts.extend(node.module.split("."))
            base = ".".join(base_parts)
        else:
            base = node.module or ""
        if base == "app" or base.startswith("app."):
            include(base)
            for alias in node.names:
                if alias.name != "*":
                    include(f"{base}.{alias.name}")
    return imports


def _reachable_import_nodes(tree: ast.Module) -> tuple[ast.Import | ast.ImportFrom, ...]:
    """Return imports from statically reachable top-level function bodies.

    Public functions are module entry points. Private functions become live
    only when a top-level expression, ``__all__``, a class, or another live
    function references them. This lets literal factory registries preserve
    their lazy implementation edges without allowing an unregistered helper
    to keep a dead module reachable.
    """
    functions = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    function_names = set(functions)

    def loaded_function_names(node: ast.AST) -> set[str]:
        return {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in function_names
        }

    roots = {name for name in function_names if not name.startswith("_")}
    imports: list[ast.Import | ast.ImportFrom] = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            header_nodes: tuple[ast.AST, ...] = (
                *statement.decorator_list,
                *statement.args.defaults,
                *(default for default in statement.args.kw_defaults if default is not None),
            )
            for header in header_nodes:
                roots.update(loaded_function_names(header))
            continue
        roots.update(loaded_function_names(statement))
        imports.extend(child for child in ast.walk(statement) if isinstance(child, (ast.Import, ast.ImportFrom)))
        if (
            isinstance(statement, (ast.Assign, ast.AnnAssign))
            and (
                isinstance(statement.target, ast.Name)
                if isinstance(statement, ast.AnnAssign)
                else len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)
            )
            and (statement.target.id if isinstance(statement, ast.AnnAssign) else statement.targets[0].id) == "__all__"
        ):
            value = statement.value
            if value is not None:
                try:
                    exported = ast.literal_eval(value)
                except (TypeError, ValueError):
                    exported = ()
                if isinstance(exported, (list, tuple)):
                    roots.update(name for name in exported if isinstance(name, str) and name in function_names)

    reachable_functions: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in reachable_functions:
            continue
        reachable_functions.add(name)
        pending.extend(loaded_function_names(functions[name]) - reachable_functions)

    for name in sorted(reachable_functions):
        imports.extend(child for child in ast.walk(functions[name]) if isinstance(child, (ast.Import, ast.ImportFrom)))
    return tuple(imports)


def _literal_handler_targets(path: Path) -> tuple[tuple[str, str], ...]:
    """Read the exact lazy CLI targets from the top-level ``_HANDLERS`` map."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(literal_string_pair_registry(tree, "_HANDLERS").values())


def _validate_handler_symbols(
    handler_path: Path = ROOT / "backend/app/cli/main.py",
    reviewed_symbols: tuple[ReviewedSymbol, ...] = _PRODUCTION_REVIEWED_SYMBOLS,
) -> None:
    """Require exact reviewed command paths and symbols to match ``_HANDLERS``."""
    expected = set(_literal_handler_targets(handler_path))
    actual = {
        (entry.path.removeprefix("backend/").removesuffix(".py").replace("/", "."), entry.symbol)
        for entry in reviewed_symbols
        if entry.symbol.startswith("cmd_")
    }
    if actual != expected:
        raise RuntimeError(
            "Vulture CLI handler evidence drifted from _HANDLERS: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )


def _protected_module_names(app_root: Path) -> set[str]:
    protected: set[str] = set()
    for exclusion in _REVIEWED_EXCLUSIONS:
        if not exclusion.protects_reachability:
            continue
        path = ROOT / exclusion.path.rstrip("/")
        candidates = path.rglob("*.py") if exclusion.path.endswith("/") else (path,)
        for candidate in candidates:
            if candidate.is_file() and candidate.is_relative_to(app_root):
                protected.add(_module_name(app_root, candidate))
    return protected


def _find_unreachable_production_modules(
    app_root: Path,
    *,
    entry_files: tuple[Path, ...] = (),
    protected_modules: set[str] | None = None,
) -> set[str]:
    """Return production modules unreachable from declared application roots."""
    module_paths = {
        _module_name(app_root, path): path for path in app_root.rglob("*.py") if "__pycache__" not in path.parts
    }
    known_modules = set(module_paths)
    graph = {
        module: _module_imports(module_name=module, path=path, known_modules=known_modules)
        for module, path in module_paths.items()
    }

    protected = protected_modules or set()
    roots = {module for module in ("app", "app.__main__") if module in known_modules} | protected
    for entry_file in entry_files:
        roots.update(
            _module_imports(
                module_name=entry_file.stem,
                path=entry_file,
                known_modules=known_modules,
            )
        )

    reachable: set[str] = set()
    pending = list(roots)
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        reachable.add(module)
        pending.extend(graph.get(module, ()) - reachable)

    return known_modules - reachable - protected


def _validate_production_reachability() -> None:
    app_root = ROOT / "backend/app"
    unreachable = _find_unreachable_production_modules(
        app_root,
        entry_files=(ROOT / "backend/export_all_rife_onnx.py",),
        protected_modules=_protected_module_names(app_root),
    )
    if unreachable:
        formatted = ", ".join(sorted(unreachable))
        raise RuntimeError(f"unreachable Python production modules: {formatted}")


def _finding_key(item: Item, *, root: Path = ROOT) -> tuple[str, str]:
    path = item.filename
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root.resolve())
        except ValueError:
            pass
    return path.as_posix(), item.name


def _scan_unused_code(
    paths: list[str | Path],
    *,
    root: Path = ROOT,
    exclusions: tuple[ReviewedExclusion, ...] = _REVIEWED_EXCLUSIONS,
) -> tuple[Item, ...]:
    scanner = Vulture()
    source_paths: set[Path] = set()
    for path in paths:
        resolved = Path(path) if Path(path).is_absolute() else root / path
        if resolved.is_dir():
            source_paths.update(resolved.rglob("*.py"))
        elif resolved.is_file():
            source_paths.add(resolved)
        else:
            raise RuntimeError(f"Vulture scan path does not exist: {resolved}")

    excluded_files = {entry.path for entry in exclusions if not entry.path.endswith("/")}
    excluded_directories = tuple(entry.path for entry in exclusions if entry.path.endswith("/"))
    for source_path in sorted(source_paths):
        relative = source_path.resolve().relative_to(root.resolve()).as_posix()
        if relative in excluded_files or any(relative.startswith(directory) for directory in excluded_directories):
            continue
        scanner.scan(source_path.read_text(encoding="utf-8"), filename=source_path)
    return tuple(scanner.get_unused_code(min_confidence=60))


def _unreviewed_findings(
    findings: tuple[Item, ...],
    reviewed_symbols: tuple[ReviewedSymbol, ...],
    *,
    root: Path = ROOT,
) -> tuple[Item, ...]:
    reviewed = {(entry.path, entry.symbol) for entry in reviewed_symbols}
    return tuple(item for item in findings if _finding_key(item, root=root) not in reviewed)


def _print_finding(item: Item, *, root: Path = ROOT) -> None:
    path, _ = _finding_key(item, root=root)
    print(f"{path}:{item.first_lineno}: {item.message} ({item.confidence}% confidence)")


def _run(
    paths: list[str],
    reviewed_symbols: tuple[ReviewedSymbol, ...],
    *,
    required_reviewed_symbols: tuple[ReviewedSymbol, ...],
) -> int:
    findings = _scan_unused_code(paths)
    observed = {_finding_key(item) for item in findings}
    required = {(entry.path, entry.symbol) for entry in required_reviewed_symbols}
    stale = sorted(required - observed)
    if stale:
        for path, symbol in stale:
            print(f"stale reviewed Python dead-code symbol: {path}::{symbol}", file=sys.stderr)
        return 3

    unreviewed = _unreviewed_findings(findings, reviewed_symbols)
    for item in unreviewed:
        _print_finding(item)
    return 3 if unreviewed else 0


def main() -> int:
    _validate_reviewed_exclusions()
    _validate_reviewed_symbols()
    _validate_handler_symbols()
    _validate_production_reachability()
    production = _run(
        [
            "backend/app",
            "backend/export_all_rife_onnx.py",
        ],
        _PRODUCTION_REVIEWED_SYMBOLS,
        required_reviewed_symbols=_PRODUCTION_REVIEWED_SYMBOLS,
    )
    if production:
        return production
    return _run(
        [
            "backend/app",
            "backend/tests",
            "backend/tests_full_e2e",
            "backend/export_all_rife_onnx.py",
            "scripts",
        ],
        (*_PRODUCTION_REVIEWED_SYMBOLS, *_FULL_SCAN_ONLY_REVIEWED_SYMBOLS),
        required_reviewed_symbols=_FULL_SCAN_ONLY_REVIEWED_SYMBOLS,
    )


if __name__ == "__main__":
    raise SystemExit(main())
