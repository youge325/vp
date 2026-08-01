"""Production-only Python import graph and command-level reachability."""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

from architecture_contracts.python_modules import python_module_name

from .reviewed import ROOT, _REVIEWED_EXCLUSIONS, ReviewedExclusion, literal_handler_targets


def _reachable_import_nodes(tree: ast.Module) -> tuple[ast.Import | ast.ImportFrom, ...]:
    """Return imports reachable from module state and live top-level functions."""
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
            headers: tuple[ast.AST, ...] = (
                *statement.decorator_list,
                *statement.args.defaults,
                *(default for default in statement.args.kw_defaults if default is not None),
            )
            for header in headers:
                roots.update(loaded_function_names(header))
            continue
        roots.update(loaded_function_names(statement))
        imports.extend(child for child in ast.walk(statement) if isinstance(child, (ast.Import, ast.ImportFrom)))
        target: ast.expr | None = None
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            target = statement.target
        elif (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            target = statement.targets[0]
        if isinstance(target, ast.Name) and target.id == "__all__" and statement.value is not None:
            try:
                exported = ast.literal_eval(statement.value)
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


def _module_imports(*, module_name: str, path: Path, known_modules: set[str]) -> set[str]:
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

    if module_name == "app.cli.main":
        for registered_module, _symbol in literal_handler_targets(path):
            if registered_module not in known_modules:
                raise RuntimeError(f"_HANDLERS references unknown production module: {registered_module}")
            include(registered_module)

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


def _protected_module_names(
    app_root: Path,
    *,
    root: Path = ROOT,
    exclusions: tuple[ReviewedExclusion, ...] = _REVIEWED_EXCLUSIONS,
) -> set[str]:
    protected: set[str] = set()
    for exclusion in exclusions:
        if not exclusion.protects_reachability:
            continue
        path = root / exclusion.path.rstrip("/")
        candidates = path.rglob("*.py") if exclusion.path.endswith("/") else (path,)
        for candidate in candidates:
            if candidate.is_file() and candidate.is_relative_to(app_root):
                protected.add(python_module_name(app_root, candidate))
    return protected


def _find_unreachable_production_modules(
    app_root: Path,
    *,
    entry_files: tuple[Path, ...] = (),
    protected_modules: set[str] | None = None,
) -> set[str]:
    """Return modules not reachable from application and explicit dynamic roots."""
    module_paths = {
        python_module_name(app_root, path): path for path in app_root.rglob("*.py") if "__pycache__" not in path.parts
    }
    known_modules = set(module_paths)
    graph = {
        module: _module_imports(module_name=module, path=path, known_modules=known_modules)
        for module, path in module_paths.items()
    }
    protected = protected_modules or set()
    roots = {module for module in ("app", "app.__main__") if module in known_modules} | protected
    for entry_file in entry_files:
        roots.update(_module_imports(module_name=entry_file.stem, path=entry_file, known_modules=known_modules))

    reachable: set[str] = set()
    pending = list(roots)
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        reachable.add(module)
        pending.extend(graph.get(module, ()) - reachable)
    return known_modules - reachable - protected


def validate_production_reachability(root: Path = ROOT) -> None:
    app_root = root / "backend/app"
    unreachable = _find_unreachable_production_modules(
        app_root,
        entry_files=(root / "backend/export_all_rife_onnx.py",),
        protected_modules=_protected_module_names(app_root, root=root),
    )
    if unreachable:
        raise RuntimeError(f"unreachable Python production modules: {', '.join(sorted(unreachable))}")


__all__ = [
    "_find_unreachable_production_modules",
    "_protected_module_names",
    "_reachable_import_nodes",
    "validate_production_reachability",
]
