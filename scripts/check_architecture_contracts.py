#!/usr/bin/env python3
"""Validate cross-layer architecture contracts for VP Workbench."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from architecture_contracts.checks import collect_architecture_issues  # noqa: E402


def main() -> int:
    try:
        issues = collect_architecture_issues(ROOT)
    except RuntimeError as exc:
        sys.stderr.write(f"[check-architecture-contracts] PARSE ERROR: {exc}\n")
        return 2

    if issues:
        sys.stderr.write("[check-architecture-contracts] DRIFT DETECTED:\n")
        for issue in issues:
            sys.stderr.write(f"  - {issue}\n")
        return 1

    sys.stdout.write("[check-architecture-contracts] OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
