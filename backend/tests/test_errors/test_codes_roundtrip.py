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

import app.__main__ as app_main
from app.errors import ProcessError
from app.errors._bootstrap import infer_error_code
from app.errors._codes import TaskErrorCode, error_code_to_wire

TASK_ERROR_CODES = {code.value for code in TaskErrorCode}


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
    assert infer_error_code(ImportError("no module named 'torch'")) == TaskErrorCode.MISSING_TENSOR_BACKEND.value


def test_infer_error_code_routes_paddle_to_missing_tensor_backend() -> None:
    assert infer_error_code(ImportError("no module named 'paddle'")) == TaskErrorCode.MISSING_TENSOR_BACKEND.value


def test_infer_error_code_routes_pyav_to_missing_python_dependency() -> None:
    """Non-tensor missing modules must map to the new MISSING_PYTHON_DEPENDENCY code.

    Previously this returned the bare string ``"missing_python_dependency"`` even
    though the enum had no such value (SSOT drift). This test pins the fix.
    """
    assert infer_error_code(ImportError("no module named 'pyav'")) == TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value


def test_infer_error_code_routes_ffmpeg_to_missing_ffmpeg() -> None:
    assert infer_error_code(FileNotFoundError("ffmpeg binary not found")) == TaskErrorCode.MISSING_FFMPEG.value
    assert infer_error_code(RuntimeError("ffprobe call failed")) == TaskErrorCode.MISSING_FFMPEG.value


def test_infer_error_code_routes_model_to_missing_model() -> None:
    assert infer_error_code(RuntimeError("model weight flownet_v4.25.pkl missing")) == TaskErrorCode.MISSING_MODEL.value


def test_infer_error_code_routes_cancel_to_cancelled() -> None:
    assert infer_error_code(RuntimeError("operation was cancelled")) == TaskErrorCode.CANCELLED.value
    assert infer_error_code(RuntimeError("operation was canceled")) == TaskErrorCode.CANCELLED.value


def test_infer_error_code_defaults_to_process_failed() -> None:
    assert infer_error_code(RuntimeError("some random failure")) == TaskErrorCode.PROCESS_FAILED.value


@pytest.mark.parametrize(
    ("raw_code", "expected_code"),
    [
        (TaskErrorCode.MISSING_MODEL, TaskErrorCode.MISSING_MODEL.value),
        (TaskErrorCode.MISSING_MODEL.value, TaskErrorCode.MISSING_MODEL.value),
        ("not_a_real_code", TaskErrorCode.PROCESS_FAILED.value),
        (None, TaskErrorCode.PROCESS_FAILED.value),
    ],
)
def test_error_code_to_wire_accepts_only_current_contract_values(raw_code: object, expected_code: str) -> None:
    assert error_code_to_wire(raw_code) == expected_code


@pytest.mark.parametrize(
    ("raw_code", "expected_code"),
    [
        (TaskErrorCode.MISSING_MODEL, TaskErrorCode.MISSING_MODEL.value),
        ("not_a_real_code", TaskErrorCode.PROCESS_FAILED.value),
    ],
)
def test_main_wire_error_code_uses_same_normalization(raw_code: object, expected_code: str) -> None:
    """Top-level ``python -m app`` envelopes must use Rust-safe wire codes."""
    assert app_main._wire_error_code(raw_code) == expected_code


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
        code = infer_error_code(RuntimeError(message))
        assert code in TASK_ERROR_CODES, f"infer_error_code({message!r}) -> {code!r} is not a real TaskErrorCode value"


# Verify the three backend error-code entry points agree.
# After collapsing the old ``_infer_code_from_exception`` wrapper, the only
# legitimate entry points are:
#   1. ``ProcessError.from_exception``           (application code path)
#   2. ``infer_error_code``                       (the bootstrap source of truth)
#   3. ``app.__main__._bootstrap_error_code``     (import-time fallback)
# All three must agree on the codes they share — otherwise an exception that
# raises during ``main()`` versus during ``import`` would surface different
# codes to the frontend.

_THREE_WAY_FIXTURES: list[tuple[BaseException, str]] = [
    (
        ImportError("No module named 'torch'"),
        TaskErrorCode.MISSING_TENSOR_BACKEND.value,
    ),
    (
        ImportError("No module named 'paddle'"),
        TaskErrorCode.MISSING_TENSOR_BACKEND.value,
    ),
    (
        ImportError("No module named 'pyav'"),
        TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value,
    ),
    (
        FileNotFoundError("ffprobe not found in PATH"),
        TaskErrorCode.MISSING_FFMPEG.value,
    ),
    (
        FileNotFoundError("ffmpeg binary missing"),
        TaskErrorCode.MISSING_FFMPEG.value,
    ),
    (
        RuntimeError("operation was cancelled by user"),
        TaskErrorCode.CANCELLED.value,
    ),
    (
        RuntimeError("flownet_v4.25.pkl is missing"),
        TaskErrorCode.MISSING_MODEL.value,
    ),
    (
        RuntimeError("totally generic failure"),
        TaskErrorCode.PROCESS_FAILED.value,
    ),
]


@pytest.mark.parametrize(("exc", "expected_code"), _THREE_WAY_FIXTURES)
def test_three_entry_points_agree(exc: BaseException, expected_code: str) -> None:
    """``ProcessError.from_exception``, ``infer_error_code``, and the
    ``__main__`` bootstrap fallback all yield the same code for the same
    exception. This is the test that catches drift between the entry
    points after consolidation."""
    from_exception_code = ProcessError.from_exception(exc).code
    bootstrap_code = infer_error_code(exc)
    main_code = app_main._bootstrap_error_code(exc)
    assert from_exception_code == expected_code
    assert bootstrap_code == expected_code
    assert main_code == expected_code


def test_main_bootstrap_uses_shared_inference_when_available() -> None:
    """The ``__main__`` fallback must prefer ``_bootstrap.infer_error_code``
    over its inline mirror so additions to the shared rule set automatically
    flow through. Verified by checking that a pattern only the shared module
    recognises (``tensor backend`` literal) is routed correctly."""
    code = app_main._bootstrap_error_code(RuntimeError("tensor backend not installed"))
    assert code == TaskErrorCode.MISSING_TENSOR_BACKEND.value


# ---------------------------------------------------------------------------
# stdlib type dispatch fallback.
# ---------------------------------------------------------------------------
# When the exception message has no recognised keyword, the resolver should
# fall through to coarse ``isinstance`` buckets so common stdlib errors get a
# more useful code than the generic ``PROCESS_FAILED``. The ``infer_error_code``
# Message matching runs before the exception-aware type dispatch.

_TYPE_DISPATCH_FIXTURES: list[tuple[BaseException, str]] = [
    (
        ImportError("cannot import name 'foo' from 'bar'"),
        TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value,
    ),
    (
        ModuleNotFoundError("import side-effect blew up"),
        TaskErrorCode.MISSING_PYTHON_DEPENDENCY.value,
    ),
    (
        FileNotFoundError("temp scratch dir vanished"),
        TaskErrorCode.IO_ERROR.value,
    ),
    (
        PermissionError("cannot open output for writing"),
        TaskErrorCode.IO_ERROR.value,
    ),
    (
        ValueError("crf must be between 0 and 51"),
        TaskErrorCode.INVALID_INPUT.value,
    ),
    (
        TypeError("preset must be a string"),
        TaskErrorCode.INVALID_INPUT.value,
    ),
    (
        RuntimeError("truly opaque failure"),
        TaskErrorCode.PROCESS_FAILED.value,
    ),
]


@pytest.mark.parametrize(("exc", "expected_code"), _TYPE_DISPATCH_FIXTURES)
def test_type_dispatch_fallback(exc: BaseException, expected_code: str) -> None:
    """No keyword in the message → fall back to ``isinstance`` buckets.

    Asserts that both ``infer_error_code(exc)`` and
    ``ProcessError.from_exception(exc)`` agree
    on the coarse bucket the type dispatch picked.
    """
    assert infer_error_code(exc) == expected_code
    assert ProcessError.from_exception(exc).code == expected_code


def test_message_match_wins_over_type_dispatch() -> None:
    """A keyword in the message must outrank the stdlib type bucket.

    ``FileNotFoundError`` would normally bucket to ``IO_ERROR``, but a
    message naming ``ffmpeg`` must still map to ``MISSING_FFMPEG`` so the
    long-standing CLI behavior is preserved.
    """
    exc = FileNotFoundError("ffmpeg binary missing")
    assert infer_error_code(exc) == TaskErrorCode.MISSING_FFMPEG.value
    exc2 = ImportError("No module named 'torch'")
    assert infer_error_code(exc2) == TaskErrorCode.MISSING_TENSOR_BACKEND.value


# ---------------------------------------------------------------------------
# MISSING_MODEL 关键字收窄。
# ---------------------------------------------------------------------------
# 原来 ``"model" in message`` 关键字太宽,任何含 "model" 字的消息都会被
# 归类为 MISSING_MODEL —— 包括 Pydantic ValidationError 里携带字段名的
# 字符串(如 ``"model_x has invalid type"``)。关键字白名单
# 收紧到 ``"flownet_v" / "model file" / "model weight" / "missing model"``,
# message-first 优先级保持不变(否则 ``FileNotFoundError("ffmpeg")`` 会
# 落到 IO_ERROR 而不是 MISSING_FFMPEG)。


def test_pydantic_validation_error_with_model_word_is_invalid_input() -> None:
    """Pydantic ValidationError 文本含 'model_x' 字段名 → 不再误归 MISSING_MODEL。

    关键字收窄后,普通的 'model' 字提及不再触发 MISSING_MODEL,
    而是按 type-dispatch fallback 走到 INVALID_INPUT(ValueError 桶)。
    """
    exc = ValueError("model_x must be one of ['4.6', '4.25']")
    assert infer_error_code(exc) == TaskErrorCode.INVALID_INPUT.value


def test_unrelated_model_mention_falls_through_to_process_failed() -> None:
    """白名单外的 'model' 字提及落到 PROCESS_FAILED。

    例如 ``"yolov8 model not loaded"`` 含 'model' 但不在白名单
    (``model file`` / ``model weight`` / ``missing model``),
    RuntimeError 也没有更具体的 type-dispatch bucket。
    """
    assert infer_error_code(RuntimeError("yolov8 model not loaded")) == TaskErrorCode.PROCESS_FAILED.value


def test_whitelisted_model_keywords_still_route_to_missing_model() -> None:
    """白名单内的 4 个变体都必须保留 MISSING_MODEL 归类(回归护栏)。"""
    assert infer_error_code(RuntimeError("flownet_v4.25.pkl not found")) == TaskErrorCode.MISSING_MODEL.value
    assert infer_error_code(RuntimeError("model file weights/rife.pkl missing")) == TaskErrorCode.MISSING_MODEL.value
    assert infer_error_code(RuntimeError("model weight tensor not initialized")) == TaskErrorCode.MISSING_MODEL.value
    assert (
        infer_error_code(RuntimeError("missing model weights for super-resolution"))
        == TaskErrorCode.MISSING_MODEL.value
    )
