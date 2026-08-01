"""Import-safe bounds for JSON subprocess protocol records."""

from __future__ import annotations

import json
from typing import Any

from app.generated.bootstrap_constants import ERROR_SUMMARY_LIMIT_BYTES, NDJSON_LINE_LIMIT_BYTES


def encode_bounded_json_line(payload: Any, *, prefix: str = "") -> str:
    """Encode one UTF-8 JSON line without crossing the manifest limit."""
    line = f"{prefix}{json.dumps(payload, ensure_ascii=False)}\n"
    encoded_size = len(line.encode("utf-8"))
    if encoded_size > NDJSON_LINE_LIMIT_BYTES:
        raise ValueError(f"Protocol line is {encoded_size} bytes; limit is {NDJSON_LINE_LIMIT_BYTES} bytes.")
    return line


def bound_error_fields(message: object, details: object) -> tuple[str, dict[str, Any]]:
    """Return JSON-safe error fields whose combined summary fits the manifest bound."""
    safe_message = str(message) or "Process failed."
    safe_details = _json_object(details)
    if _error_summary_size(safe_message, safe_details) <= ERROR_SUMMARY_LIMIT_BYTES:
        return safe_message, safe_details

    diagnostic = json.dumps(safe_details, ensure_ascii=False, separators=(",", ":"))
    safe_message = _truncate_utf8(safe_message, min(2048, ERROR_SUMMARY_LIMIT_BYTES // 4))
    bounded_details: dict[str, Any] = {
        "truncated": True,
        "summary": _truncate_utf8(diagnostic, ERROR_SUMMARY_LIMIT_BYTES),
    }
    while _error_summary_size(safe_message, bounded_details) > ERROR_SUMMARY_LIMIT_BYTES:
        summary = bounded_details["summary"]
        assert isinstance(summary, str)
        excess = _error_summary_size(safe_message, bounded_details) - ERROR_SUMMARY_LIMIT_BYTES
        bounded_details["summary"] = _truncate_utf8(summary, max(len(summary.encode("utf-8")) - excess - 1, 0))
    return safe_message, bounded_details


def _json_object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"diagnostic": _safe_repr(value)}
    try:
        rendered = json.dumps(value, ensure_ascii=False)
        parsed = json.loads(rendered)
    except (TypeError, ValueError, RecursionError):
        return {"diagnostic": _safe_repr(value)}
    return parsed


def _safe_repr(value: object) -> str:
    try:
        return repr(value)
    except BaseException:  # pragma: no cover - hostile exception payload boundary
        return f"<{type(value).__name__}>"


def _error_summary_size(message: str, details: dict[str, Any]) -> int:
    return len(
        json.dumps(
            {"message": message, "details": details},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _truncate_utf8(value: str, limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    if limit <= 0:
        return ""
    suffix = "…"
    suffix_bytes = suffix.encode("utf-8")
    if limit < len(suffix_bytes):
        return encoded[:limit].decode("utf-8", errors="ignore")
    return encoded[: limit - len(suffix_bytes)].decode("utf-8", errors="ignore") + suffix
