"""Architecture guards for the neutral media ports and FFmpeg adapter."""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_planning_and_processing_depend_on_media_ports_not_ffmpeg() -> None:
    offenders: list[str] = []
    for package in ("planning", "processing"):
        for path in (APP_ROOT / package).rglob("*.py"):
            if any(module.startswith("app.utils.ffmpeg") for module in _imports(path)):
                offenders.append(path.relative_to(APP_ROOT).as_posix())

    assert offenders == []


def test_media_ports_have_explicit_signatures_without_any_or_variadics() -> None:
    path = APP_ROOT / "ports" / "media.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    assert "Any" not in source
    variadics = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (node.args.vararg is not None or node.args.kwarg is not None)
    ]
    assert variadics == []
