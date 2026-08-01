from __future__ import annotations

from typing import Any

import pytest

import app.__main__ as app_main
import app.cli.main
import app.protocol.emitter
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from app.generated.contracts import BackendTaskErrorPayload
from app.generated.protocol_constants import BackendEnvelopeType


def _run_with_failure(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> list[tuple[BackendEnvelopeType, BackendTaskErrorPayload]]:
    captured: list[tuple[BackendEnvelopeType, BackendTaskErrorPayload]] = []

    def fail() -> None:
        raise exc

    monkeypatch.setattr(app.cli.main, "main", fail)
    monkeypatch.setattr(
        app.protocol.emitter.ndjson,
        "emit",
        lambda event_type, payload: captured.append((event_type, payload)),
    )

    with pytest.raises(SystemExit) as exit_info:
        app_main._run()

    assert exit_info.value.code == 1
    return captured


def test_process_error_uses_typed_ndjson_emitter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _run_with_failure(
        monkeypatch,
        ProcessError(
            TaskErrorCode.INVALID_CONFIG,
            "bad config",
            details={"section": "workflow"},
        ),
    )

    assert captured[0][0] is BackendEnvelopeType.ERROR
    assert captured[0][1].model_dump(mode="json") == {
        "code": "invalid_config",
        "message": "bad config",
        "details": {"section": "workflow"},
    }


def test_unexpected_error_uses_typed_ndjson_emitter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _run_with_failure(monkeypatch, RuntimeError("ffmpeg executable missing"))

    assert len(captured) == 1
    event_type, payload = captured[0]
    assert event_type is BackendEnvelopeType.ERROR
    assert payload.code == TaskErrorCode.MISSING_FFMPEG
    assert payload.message == "ffmpeg executable missing"
    assert payload.details is not None
    assert "traceback" in payload.details


def test_import_safe_fallback_builds_bootstrap_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[object, str, dict[str, Any]]] = []
    monkeypatch.setattr(
        app_main,
        "_emit_error_payload",
        lambda code, message, details: captured.append((code, message, details)),
    )

    try:
        raise RuntimeError("ffmpeg bootstrap failure")
    except RuntimeError as exc:
        app_main._emit_unhandled_exception(exc)

    assert len(captured) == 1
    code, message, details = captured[0]
    assert code == "missing_ffmpeg"
    assert message == "ffmpeg bootstrap failure"
    assert details["exception"] == "RuntimeError"
    assert "RuntimeError: ffmpeg bootstrap failure" in details["traceback"]
