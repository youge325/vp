"""Restricted Rust visibility must be justified by production consumers."""

from __future__ import annotations

import re
from pathlib import Path

from .rules import read_source, relative_path

_DECLARATION = re.compile(
    r"^\s*pub\((?:crate|super)\)\s+(?:async\s+)?"
    r"(?:const|static|fn|struct|enum|type|trait|mod)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _production_rust_source(text: str) -> str:
    marker = re.search(r"^\s*#\s*\[cfg\(test\)\]\s*\n", text, flags=re.MULTILINE)
    return text[: marker.start()] if marker else text


def _top_level_restricted_declarations(text: str) -> list[tuple[str, int]]:
    declarations: list[tuple[str, int]] = []
    depth = 0
    line_start = 0
    for line in text.splitlines(keepends=True):
        if depth == 0:
            match = _DECLARATION.match(line)
            if match and "#[tauri::command]" not in text[max(0, line_start - 160) : line_start]:
                declarations.append((match.group(1), line_start + match.start(1)))
        depth += line.count("{") - line.count("}")
        line_start += len(line)
    return declarations


def check_rust_restricted_visibility(root: Path) -> list[str]:
    rust_root = root / "frontend/src-tauri/src"
    sources: dict[Path, str] = {
        path: _production_rust_source(read_source(path, root))
        for path in sorted(rust_root.rglob("*.rs"))
        if "generated" not in path.parts
        and "tests" not in path.parts
        and path.name not in {"test_support.rs", "tests.rs"}
    }
    combined = "\n".join(sources.values())
    issues: list[str] = []
    for path, source in sources.items():
        for name, offset in _top_level_restricted_declarations(source):
            occurrences = len(re.findall(rf"\b{re.escape(name)}\b", combined))
            if occurrences <= 1:
                line = source.count("\n", 0, offset) + 1
                issues.append(
                    f"restricted Rust symbol has no production consumer: {relative_path(path, root)}:{line} `{name}`"
                )
    return issues
