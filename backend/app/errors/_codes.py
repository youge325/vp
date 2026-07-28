"""Helpers around the generated backend error-code contract."""

from __future__ import annotations

from typing import Any

from app.generated.contracts import BackendTaskErrorCode as TaskErrorCode

_ALL_CODES = frozenset(code.value for code in TaskErrorCode)


def error_code_to_wire(code: Any) -> str:
    """Return a Rust-schema-safe snake_case task error code.

    The NDJSON wire protocol accepts generated enum values or current schema
    strings. Unknown values degrade to ``process_failed``.
    """
    if isinstance(code, TaskErrorCode):
        return code.value

    if isinstance(code, str):
        stripped = code.strip()
        if stripped in _ALL_CODES:
            return stripped
    return TaskErrorCode.PROCESS_FAILED.value
