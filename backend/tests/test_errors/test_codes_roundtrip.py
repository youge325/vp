"""Round-trip tests for TaskErrorCode SSOT.

Ensures every ``TaskErrorCode`` enum value flows cleanly through:
1. ``ProcessError`` construction
2. JSON serialization (same shape ``__main__._emit`` produces)
3. Re-parsing back to a string code

Also covers ``_bootstrap.infer_error_code`` pattern matching to guard
against silent drift between bootstrap fallbacks and the enum SSOT.
"""

from __future__ import annotations

import json

import pytest

from app.errors import ProcessError
from app.errors._bootstrap import infer_error_code
from app.errors._codes import ALL_CODES, TaskErrorCode


@pytest.mark.parametrize("code", list(TaskErrorCode))
def test_every_code_round_trips_through_json(code: TaskErrorCode) -> None:
    """Each enum value survives JSON round-trip as the same snake_case string."""
    exc = ProcessError(code, "diagnostic message")
    payload = {
        "type": "error",
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
    }
    encoded = json.dumps(payload, ensure_ascii=False)
    decoded = json.loads(encoded)
    assert decoded["code"] == code.value
    assert decoded["message"] == "diagnostic message"


def test_infer_error_code_routes_torch_to_missing_tensor_backend() -> None:
    assert infer_error_code("no module named 'torch'") == TaskErrorCode.MISSING_TENSOR_BACKEND.value


def test_infer_error_code_routes_paddle_to_missing_tensor_backend() -> None:
    assert infer_error_code("no module named 'paddle'") == TaskErrorCode.MISSING_TENSOR_BACKEND.value


def test_infer_error_code_routes_pyav_to_missing_python_dependency() -> None:
    """Non-tensor missing modules must map to the new MISSING_PYTHON_DEPENDENCY code.

    Before Phase A this returned the bare string ``"missing_python_dependency"`` even
    though the enum had no such value (SSOT drift). This test pins the fix.
    """
    assert infer_error_code("no module named 'pyav'") == TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value


def test_infer_error_code_routes_ffmpeg_to_missing_ffmpeg() -> None:
    assert infer_error_code("ffmpeg binary not found") == TaskErrorCode.MISSING_FFMPEG.value
    assert infer_error_code("ffprobe call failed") == TaskErrorCode.MISSING_FFMPEG.value


def test_infer_error_code_routes_model_to_missing_model() -> None:
    assert infer_error_code("model weight flownet_v4.25.pkl missing") == TaskErrorCode.MISSING_MODEL.value


def test_infer_error_code_routes_cancel_to_cancelled() -> None:
    assert infer_error_code("operation was cancelled") == TaskErrorCode.CANCELLED.value
    assert infer_error_code("operation was canceled") == TaskErrorCode.CANCELLED.value


def test_infer_error_code_defaults_to_process_failed() -> None:
    assert infer_error_code("some random failure") == TaskErrorCode.PROCESS_FAILED.value


def test_all_codes_match_enum() -> None:
    """The ``ALL_CODES`` frozenset must exactly enumerate the enum values."""
    assert ALL_CODES == {code.value for code in TaskErrorCode}


def test_all_inferred_codes_are_in_enum() -> None:
    """Every code ``infer_error_code`` can return must be a real enum value.

    Guards against typos where the inference rule returns a string the enum
    doesn't know about.
    """
    candidate_messages = [
        "ffmpeg binary missing",
        "ffprobe call failed",
        "flownet_v4.25.pkl missing",
        "missing model weight",
        "no module named 'torch'",
        "no module named 'paddle'",
        "no module named 'pyav'",
        "tensor backend not installed",
        "operation cancelled",
        "operation canceled",
        "some random failure",
    ]
    for message in candidate_messages:
        code = infer_error_code(message)
        assert code in ALL_CODES, f"infer_error_code({message!r}) -> {code!r} is not a real TaskErrorCode value"


def test_phase_a_new_codes_are_present() -> None:
    """Sanity: Phase A explicitly adds 6 new codes."""
    new_codes = {
        TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value,
        TaskErrorCode.SPAWN_FAILED.value,
        TaskErrorCode.RUNTIME_PANIC.value,
        TaskErrorCode.IO_ERROR.value,
        TaskErrorCode.SCHEMA_MISMATCH.value,
        TaskErrorCode.PERSISTENCE_FAILED.value,
    }
    assert new_codes.issubset(ALL_CODES)
