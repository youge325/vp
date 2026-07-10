from __future__ import annotations

from typing import Any

import pytest

import app.__main__ as app_main
import app.cli
import app.protocol
from app.errors import ProcessError, TaskErrorCode


def _run_with_failure(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def fail() -> None:
        raise exc

    monkeypatch.setattr(app.cli, "main", fail)
    monkeypatch.setattr(app.protocol.ndjson, "error", lambda **payload: captured.append(payload))

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

    assert captured == [
        {
            "code": "invalid_config",
            "message": "bad config",
            "details": {"section": "workflow"},
        }
    ]


def test_unexpected_error_uses_typed_ndjson_emitter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _run_with_failure(monkeypatch, RuntimeError("ffmpeg executable missing"))

    assert len(captured) == 1
    assert captured[0]["code"] == "missing_ffmpeg"
    assert captured[0]["message"] == "ffmpeg executable missing"
    assert "traceback" in captured[0]["details"]
