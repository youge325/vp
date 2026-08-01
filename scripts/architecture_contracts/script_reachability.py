"""Reachability analysis for repository automation scripts."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from .rules import read_source, relative_path

_SCRIPT_SUFFIXES = {".py", ".ps1"}


def _script_files(root: Path) -> set[Path]:
    scripts_root = root / "scripts"
    return {path.resolve() for path in scripts_root.rglob("*") if path.is_file() and path.suffix in _SCRIPT_SUFFIXES}


def _entrypoint_references(root: Path) -> set[Path]:
    references: set[Path] = set()
    source_paths = [root / ".pre-commit-config.yaml", *sorted((root / ".github/workflows").glob("*.y*ml"))]
    package_json = root / "frontend/package.json"
    if package_json.is_file():
        package = json.loads(read_source(package_json, root))
        source_texts = [*package.get("scripts", {}).values()]
    else:
        source_texts = []
    source_texts.extend(read_source(path, root) for path in source_paths if path.is_file())
    for source in source_texts:
        for match in re.finditer(r"(?<![\w.-])(scripts[/\\][\w./\\-]+\.(?:py|ps1))(?![\w.-])", source):
            candidate = (root / match.group(1).replace("\\", "/")).resolve()
            if candidate.is_file():
                references.add(candidate)
    return references


def _python_dependencies(path: Path, scripts_root: Path) -> set[Path]:
    dependencies: set[Path] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative_module = path.relative_to(scripts_root).with_suffix("")
    module_parts = relative_module.parts
    package_parts = module_parts[:-1]
    for node in ast.walk(tree):
        modules: list[tuple[str, ...]] = []
        if isinstance(node, ast.Import):
            modules.extend(tuple(alias.name.split(".")) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level:
                retained = max(0, len(package_parts) - (node.level - 1))
                base_module = (*package_parts[:retained], *node.module.split("."))
            else:
                base_module = tuple(node.module.split("."))
            modules.append(base_module)
            modules.extend((*base_module, alias.name) for alias in node.names if alias.name != "*")
        for module in modules:
            relative = Path(*module)
            candidates = (scripts_root / f"{relative}.py", scripts_root / relative / "__init__.py")
            dependencies.update(candidate.resolve() for candidate in candidates if candidate.is_file())
    return dependencies


def _powershell_dependencies(path: Path) -> set[Path]:
    source = path.read_text(encoding="utf-8")
    names = set(
        re.findall(
            r"(?:Join-Path\s+\$PSScriptRoot\s+[\"']([^\"']+\.ps1)[\"']|"
            r"\$PSScriptRoot[/\\]([\w.-]+\.ps1))",
            source,
            flags=re.IGNORECASE,
        )
    )
    dependencies: set[Path] = set()
    for pair in names:
        name = next((value for value in pair if value), "")
        candidate = (path.parent / name).resolve()
        if candidate.is_file():
            dependencies.add(candidate)
    return dependencies


def check_script_reachability(root: Path) -> list[str]:
    scripts = _script_files(root)
    roots = _entrypoint_references(root)
    dependencies: dict[Path, set[Path]] = {}
    scripts_root = (root / "scripts").resolve()
    for path in scripts:
        if path.suffix == ".py":
            dependencies[path] = _python_dependencies(path, scripts_root)
        else:
            dependencies[path] = _powershell_dependencies(path)

    reachable: set[Path] = set()
    pending = list(roots)
    while pending:
        path = pending.pop()
        if path in reachable:
            continue
        reachable.add(path)
        pending.extend(dependencies.get(path, set()) - reachable)

    return [
        f"unreachable repository script: {relative_path(path, root)}"
        for path in sorted(scripts - reachable)
        if path.name != "__init__.py" or path.parent.resolve() not in {item.parent for item in reachable}
    ]
