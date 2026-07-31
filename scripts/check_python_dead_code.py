#!/usr/bin/env python3
"""Run production-only and full-suite Vulture gates."""

from __future__ import annotations

import ast
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class ReviewedExclusion:
    path: str
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

    for node in ast.walk(tree):
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


def _protected_module_names(app_root: Path) -> set[str]:
    protected: set[str] = set()
    for exclusion in _REVIEWED_EXCLUSIONS:
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


def _run(paths: list[str]) -> int:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vulture",
            *paths,
            "--min-confidence",
            "60",
            "--exclude",
            ",".join(entry.path for entry in _REVIEWED_EXCLUSIONS),
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


def main() -> int:
    _validate_reviewed_exclusions()
    _validate_production_reachability()
    production = _run(
        [
            "backend/app",
            "backend/export_all_rife_onnx.py",
            "backend/vulture_whitelist.py",
        ]
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
            "backend/vulture_whitelist.py",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
