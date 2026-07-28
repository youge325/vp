"""Shared NDJSON assertions for CLI subprocess tests."""

from __future__ import annotations

import json
from typing import Any


def last_json_object(stdout: str) -> dict[str, Any]:
    """Return the last JSON object line, ignoring diagnostics and blank lines."""
    for line in reversed(stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise AssertionError(f"No JSON object line found in stdout:\n{stdout}")
