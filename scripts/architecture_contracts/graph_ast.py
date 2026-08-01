"""Shared graph, AST, and source parsing primitives for architecture checks."""

from __future__ import annotations

import ast
from pathlib import Path

from .rules import ContractParseError, read_source, relative_path


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
