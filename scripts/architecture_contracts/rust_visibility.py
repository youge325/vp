"""Restricted Rust visibility must be justified by cross-module production consumers."""

from __future__ import annotations

import re
from pathlib import Path

from .rules import read_source, relative_path
from .rust_source import production_rust_source

_DECLARATION = re.compile(
    r"^\s*pub\((?:crate|super)\)\s+(?:async\s+)?"
    r"(?P<kind>const\s+fn|const|static|fn|struct|enum|type|trait|mod)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
_USE = re.compile(r"(?:^|\n)\s*(?:pub(?:\([^)]*\))?\s+)?use\s+(.+?);", re.DOTALL)
_PATH = re.compile(r"\b(?:crate|self|super|[A-Za-z_][A-Za-z0-9_]*)(?:::[A-Za-z_][A-Za-z0-9_]*)+")


def _top_level_restricted_declarations(text: str) -> list[tuple[str, str, int]]:
    declarations: list[tuple[str, str, int]] = []
    depth = 0
    line_start = 0
    for line in text.splitlines(keepends=True):
        if depth == 0:
            match = _DECLARATION.match(line)
            if match and "#[tauri::command]" not in text[max(0, line_start - 160) : line_start]:
                declarations.append((match.group("kind"), match.group("name"), line_start + match.start("name")))
        depth += line.count("{") - line.count("}")
        line_start += len(line)
    return declarations


def _module_path(path: Path, rust_root: Path) -> tuple[str, ...]:
    relative = path.relative_to(rust_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] in {"lib", "main"}:
        return ()
    if parts[-1] == "mod":
        parts.pop()
    return tuple(parts)


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(value):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _first_top_level_brace(value: str) -> int | None:
    depth = 0
    for index, character in enumerate(value):
        if character == "{" and depth == 0:
            return index
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
    return None


def _expand_use_tree(value: str, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    entries = _split_top_level(value)
    if len(entries) > 1:
        return [expanded for entry in entries for expanded in _expand_use_tree(entry, prefix)]
    if not entries:
        return []
    entry = entries[0]
    brace = _first_top_level_brace(entry)
    if brace is not None:
        base = entry[:brace].strip().removesuffix("::")
        closing = entry.rfind("}")
        if closing < brace:
            return []
        base_segments = tuple(segment for segment in base.split("::") if segment)
        return _expand_use_tree(entry[brace + 1 : closing], (*prefix, *base_segments))
    target, separator, alias = entry.partition(" as ")
    segments = (*prefix, *(segment for segment in target.strip().split("::") if segment))
    if not segments:
        return []
    local_name = alias.strip() if separator else (segments[-2] if segments[-1] == "self" else segments[-1])
    return [(segments, local_name)]


def _resolve_path(module: tuple[str, ...], segments: tuple[str, ...], *, expression: bool = False) -> tuple[str, ...]:
    remaining = list(segments)
    if not remaining:
        return ()
    if remaining[0] == "crate":
        base: list[str] = []
        remaining.pop(0)
    elif remaining[0] == "self":
        base = list(module)
        remaining.pop(0)
    elif remaining[0] == "super":
        base = list(module)
        while remaining and remaining[0] == "super":
            if base:
                base.pop()
            remaining.pop(0)
    else:
        base = list(module) if expression else []
    return (*base, *remaining)


def _resolved_use_targets(source: str, module: tuple[str, ...]) -> list[tuple[tuple[str, ...], str]]:
    return [
        (_resolve_path(module, segments, expression=True), alias)
        for match in _USE.finditer(source)
        for segments, alias in _expand_use_tree(match.group(1))
    ]


def _has_external_consumer(
    target: tuple[str, ...],
    sources: dict[Path, tuple[tuple[str, ...], str]],
    declaration_path: Path,
    *,
    is_module: bool,
) -> bool:
    name = target[-1]
    for path, (module, source) in sources.items():
        if path == declaration_path:
            continue
        imports = _resolved_use_targets(source, module)
        aliases: dict[str, list[tuple[str, ...]]] = {}
        for imported, alias in imports:
            aliases.setdefault(alias, []).append(imported)
        for imported, _alias in imports:
            if imported == target or (is_module and imported[: len(target)] == target):
                return True
            if imported and imported[-1] == "*" and imported[:-1] == target[:-1] and re.search(rf"\b{name}\b", source):
                return True
        for match in _PATH.finditer(source):
            segments = tuple(match.group(0).split("::"))
            for alias_target in aliases.get(segments[0], []):
                aliased = (*alias_target, *segments[1:])
                if aliased == target or (is_module and aliased[: len(target)] == target):
                    return True
            expression_target = _resolve_path(module, segments, expression=True)
            root_target = _resolve_path(module, segments)
            if expression_target == target or root_target == target:
                return True
            if is_module and (expression_target[: len(target)] == target or root_target[: len(target)] == target):
                return True
    return False


def check_rust_restricted_visibility(root: Path) -> list[str]:
    rust_root = root / "frontend/src-tauri/src"
    sources: dict[Path, tuple[tuple[str, ...], str]] = {}
    for path in sorted(rust_root.rglob("*.rs")):
        if "generated" in path.parts or "tests" in path.parts or path.name in {"test_support.rs", "tests.rs"}:
            continue
        source = read_source(path, root)
        if source.lstrip().startswith("// Generated from contracts/"):
            continue
        sources[path] = (_module_path(path, rust_root), production_rust_source(source))
    issues: list[str] = []
    for path, (module, source) in sources.items():
        for kind, name, offset in _top_level_restricted_declarations(source):
            target = (*module, name)
            if not _has_external_consumer(target, sources, path, is_module=kind == "mod"):
                line = source.count("\n", 0, offset) + 1
                issues.append(
                    f"restricted Rust symbol has no cross-module production consumer: "
                    f"{relative_path(path, root)}:{line} `{name}`"
                )
    return issues
