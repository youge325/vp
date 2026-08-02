"""Filter defaults and field constraints must come from neutral contracts."""

from __future__ import annotations

import re
from pathlib import Path

from .rules import read_source, relative_path

_REQUIRED_FILTER_CONSUMERS = {
    "frontend/src/services/filters/filter-catalog.ts": "FILTER_FIELD_CONSTRAINTS",
    "frontend/src/services/filters/anime-cleanup.ts": "FILTER_FIELD_CONSTRAINTS",
    "frontend/src/components/filter-steps/FilterScale.vue": "FILTER_FIELD_CONSTRAINTS",
}

_HARDCODED_BOUND = re.compile(r"(?:\b(?:min|max)\s*:\s*|:(?:min|max)\s*=\s*[\"'])[-+]?\d+(?:\.\d+)?")


def check_filter_contract_consumers(root: Path) -> list[str]:
    issues: list[str] = []
    for path_name, marker in _REQUIRED_FILTER_CONSUMERS.items():
        path = root / path_name
        if not path.is_file():
            issues.append(f"missing filter-contract consumer: {path_name}")
            continue
        if marker not in read_source(path, root):
            issues.append(f"filter constraint consumer bypasses generated metadata: {path_name}")

    for relative_root in (
        "frontend/src/services/filters",
        "frontend/src/components/filter-steps",
    ):
        search_root = root / relative_root
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*")):
            if not path.is_file() or path.suffix not in {".ts", ".tsx", ".vue"}:
                continue
            source = read_source(path, root)
            for match in _HARDCODED_BOUND.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                issues.append(
                    f"filter constraint is hard-coded instead of generated: {relative_path(path, root)}:{line}"
                )
    return issues
