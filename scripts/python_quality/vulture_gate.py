"""Vulture scanning with exact, evidence-backed dynamic symbol reviews."""

from __future__ import annotations

import sys
from pathlib import Path

from vulture import Vulture
from vulture.core import Item

from .reviewed import ROOT, _REVIEWED_EXCLUSIONS, ReviewedExclusion, ReviewedSymbol


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
    path, _symbol = _finding_key(item, root=root)
    print(f"{path}:{item.first_lineno}: {item.message} ({item.confidence}% confidence)")


def run_vulture_gate(
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


__all__ = ["_finding_key", "_scan_unused_code", "_unreviewed_findings", "run_vulture_gate"]
