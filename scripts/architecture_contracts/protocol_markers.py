"""Require cross-process marker literals to come from the neutral manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .rules import ContractParseError, read_source, relative_path
from .rust_source import production_rust_source

_MARKER_LITERAL = re.compile(r"(?P<quote>['\"])(?P<value>\[VP_[A-Z0-9_]+\]|VP_[A-Z0-9_]+\s)(?P=quote)")
_SOURCE_ROOTS = (
    ("backend/app", frozenset({".py"})),
    ("frontend/src", frozenset({".ts", ".tsx", ".vue"})),
    ("frontend/src-tauri/src", frozenset({".rs"})),
)
_GENERATED_MARKER_BINDINGS = frozenset({"frontend/src/types/protocol/events.ts"})


def check_protocol_marker_literals(root: Path) -> list[str]:
    manifest_path = root / "contracts/ipc-manifest.json"
    try:
        manifest = json.loads(read_source(manifest_path, root))
        declared = frozenset(manifest["protocolConstants"].values())
    except (json.JSONDecodeError, KeyError, AttributeError) as exc:
        raise ContractParseError("invalid protocolConstants in contracts/ipc-manifest.json") from exc

    issues: list[str] = []
    for relative_root, suffixes in _SOURCE_ROOTS:
        source_root = root / relative_root
        if not source_root.is_dir():
            raise ContractParseError(f"missing reference root: {relative_root}")
        for path in sorted(source_root.rglob("*")):
            source_path = relative_path(path, root)
            if (
                not path.is_file()
                or path.suffix not in suffixes
                or "generated" in path.parts
                or source_path in _GENERATED_MARKER_BINDINGS
            ):
                continue
            source = read_source(path, root)
            if path.suffix == ".rs":
                source = production_rust_source(source)
            for match in _MARKER_LITERAL.finditer(source):
                line_text = source[source.rfind("\n", 0, match.start()) + 1 : source.find("\n", match.end())]
                if line_text.lstrip().startswith(("#", "//", "*")):
                    continue
                value = match.group("value")
                kind = "hard-coded" if value in declared else "undeclared"
                line = source.count("\n", 0, match.start()) + 1
                issues.append(f"{kind} protocol marker `{value}`: {source_path}:{line}")
    return issues


__all__ = ["check_protocol_marker_literals"]
