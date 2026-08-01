from __future__ import annotations

import json

from app import __main__ as app_main
from app.generated.bootstrap_constants import ERROR_SUMMARY_LIMIT_BYTES, NDJSON_LINE_LIMIT_BYTES
from app.protocol.encoding import bound_error_fields


def test_bootstrap_error_is_json_safe_and_bounded(capsys) -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic

    app_main._emit_error_payload("process_failed", "界" * NDJSON_LINE_LIMIT_BYTES, cyclic)

    line = capsys.readouterr().out
    payload = json.loads(line)
    assert payload["type"] == "error"
    assert payload["details"]["truncated"] is True
    assert len(line.encode("utf-8")) <= NDJSON_LINE_LIMIT_BYTES
    summary = json.dumps(
        {"message": payload["message"], "details": payload["details"]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert len(summary.encode("utf-8")) <= ERROR_SUMMARY_LIMIT_BYTES


def test_error_bound_preserves_small_structured_details() -> None:
    message, details = bound_error_fields("missing model", {"path": "model.onnx"})

    assert message == "missing model"
    assert details == {"path": "model.onnx"}
