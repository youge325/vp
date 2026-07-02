"""测试入口包装 ``scripts/check_error_code_drift.py``。

让 ``pytest backend/tests`` 在本地与 CI 都能跑这个三层漂移检查,而不仅依赖
``pre-commit``——后者只有在用户本地装了 hook 时才生效。

CI 注意事项:
``frontend/src/types/generated/TaskErrorCode.ts`` 由 ``ts-rs`` 在 ``cargo test``
时生成。CI 上 backend-only 的 pytest 阶段往往**先于** Rust 编译,此时生成文件
还不存在,我们用 ``pytest.skip`` 直接跳过本组测试 —— 真正的漂移检测在 Rust
job 中通过 cargo test 阶段重新生成 + lib.rs::tests 触发,不依赖此处。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_error_code_drift.py"
TS_GENERATED_PATH = REPO_ROOT / "frontend" / "src" / "types" / "generated" / "TaskErrorCode.ts"

_TS_GENERATED_MISSING_MESSAGE = (
    "frontend/src/types/generated/TaskErrorCode.ts 不存在 — 通常意味着这次 CI run "
    "还没跑过 `cargo test`(ts-rs 是 cargo 端的派生宏)。漂移检测需要这个生成文件,"
    "因此本组测试在该环境下跳过 —— Rust job 的 cargo test 阶段会重新生成并对漂移做断言。"
)


def _load_module():
    """动态加载脚本,避免脚本目录加 ``__init__.py``。"""
    spec = importlib.util.spec_from_file_location("check_error_code_drift", SCRIPT_PATH)
    assert spec and spec.loader, "脚本路径不可加载"
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_error_code_drift"] = module
    spec.loader.exec_module(module)
    return module


def _require_ts_generated() -> None:
    if not TS_GENERATED_PATH.exists():
        pytest.skip(_TS_GENERATED_MISSING_MESSAGE)


def test_drift_script_exists() -> None:
    assert SCRIPT_PATH.exists(), f"漂移检测脚本缺失: {SCRIPT_PATH}"


def test_three_layers_consistent() -> None:
    """三层 TaskErrorCode 完全一致。

    如果失败,通常意味着:
    - Rust 端新增了 variant 但忘了同步 Python ``_codes.py``
    - 或在 src-tauri 改了 enum 后忘了跑 ``cargo test``(ts-rs 自动生成)
    """
    _require_ts_generated()
    module = _load_module()
    rust = module._collect_rust_task_error_codes(module._read(module.RUST_TASK_PATH))
    python = module._collect_python_codes(module._read(module.PY_PATH))
    ts = module._collect_ts_codes_from_task_error_code_file(
        module._read(module.TS_TASK_ERROR_CODE_PATH),
    )

    issues = module._diff_task_error_code(rust, python, ts)
    assert not issues, "TaskErrorCode 三层漂移:\n  - " + "\n  - ".join(issues)
    # 双重保险:确保解析到了真实数据,而不是空集合互等
    assert len(rust) >= 8, f"Rust codes 数量过少({len(rust)}),解析可能失败"


def test_script_exits_zero_when_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端跑一遍 ``main()`` 入口,验证 exit code 与 stdout 提示。"""
    _require_ts_generated()
    module = _load_module()
    exit_code = module.main()
    assert exit_code == 0


# Phase 9 — NdjsonEnvelope ↔ NdjsonEventType handshake.
#
# Python ``class NdjsonEventType`` is the superset (stream + oneshot
# emit). Rust ``enum NdjsonEnvelope`` only decodes the stream subset.
# Anything in Python that Rust doesn't decode must be on the oneshot
# whitelist. The next four tests cover the consistent state + the three
# drift directions.


def test_ndjson_envelope_handshake_consistent() -> None:
    """当前仓库状态下:Rust envelope ⊆ Python NdjsonEventType,差集 == 白名单。"""
    module = _load_module()
    py_events = module._collect_python_ndjson_event_types(module._read(module.PY_PROTOCOL_PATH))
    rust_wires = module._collect_rust_envelope_wire_names(module._read(module.RUST_ENVELOPE_PATH))

    issues = module._diff_ndjson_event_types(py_events, rust_wires)
    assert not issues, "NdjsonEnvelope ↔ NdjsonEventType 漂移:\n  - " + "\n  - ".join(issues)

    # Sanity: extracted real data, not empty intersections.
    assert len(rust_wires) >= 4, f"Rust envelope wires too few ({rust_wires})"
    assert len(py_events) >= len(rust_wires) + 3, (
        f"expected at least 3 oneshot-only events on the Python side, got py={py_events!r} rust={rust_wires!r}"
    )


def test_diff_flags_rust_variant_missing_from_python() -> None:
    """Rust 有 Python 没有的 wire 名 — 后端不会发,但 readers 期待会发。"""
    module = _load_module()
    issues = module._diff_ndjson_event_types(
        python={"progress", "completed", "error", "resume_status", "info", "check", "resume_inspection"},
        rust_envelope={"progress", "completed", "error", "resume_status", "newly_added_event"},
    )
    assert any("only-in-rust" in issue and "newly_added_event" in issue for issue in issues), issues


def test_diff_flags_unwhitelisted_python_event() -> None:
    """Python 多出 Rust 不识别且不在白名单的事件 — 真漂移。"""
    module = _load_module()
    issues = module._diff_ndjson_event_types(
        python={"progress", "completed", "error", "resume_status", "info", "check", "resume_inspection", "verbose"},
        rust_envelope={"progress", "completed", "error", "resume_status"},
    )
    assert any("unexpected" in issue.lower() and "verbose" in issue for issue in issues), issues


def test_diff_flags_whitelist_event_removed_from_python() -> None:
    """白名单里的事件从 Python 删了 — 白名单与现实不一致,需要更新脚本。"""
    module = _load_module()
    issues = module._diff_ndjson_event_types(
        python={"progress", "completed", "error", "resume_status", "info", "check"},  # 删掉 resume_inspection
        rust_envelope={"progress", "completed", "error", "resume_status"},
    )
    assert any("resume_inspection" in issue for issue in issues), issues


# Phase 18 — outputDir 三层必填一致性硬验证回归护栏。


def test_output_dir_consistency_passes_for_valid_setup() -> None:
    """Rust ``Option<String>`` + Python ``str | None = Field(default=None, min_length=1)``
    都到位时,应该返回空 issues 列表。"""
    module = _load_module()
    rust_text = (
        "pub struct OutputConfig {\n"
        "    pub output_dir: Option<String>,\n"
        "    pub open_on_complete: bool,\n"
        "    pub segment_frames: u64,\n"
        "}"
    )
    py_text = (
        "class OutputConfig(_CamelBase):\n"
        "    output_dir: str | None = Field(default=None, min_length=1)\n"
        "    open_on_complete: bool\n"
    )
    issues = module._diff_output_dir_optional_consistency(rust_text, py_text)
    assert issues == []


def test_output_dir_consistency_flags_rust_non_optional() -> None:
    """Rust 回退到 ``String``(非 Option)— Phase 18 wire 形状漂移,需要 fail。"""
    module = _load_module()
    rust_text = "pub struct OutputConfig {\n    pub output_dir: String,\n}"
    py_text = "class OutputConfig(_CamelBase):\n    output_dir: str | None = Field(default=None, min_length=1)\n"
    issues = module._diff_output_dir_optional_consistency(rust_text, py_text)
    assert any("Rust" in issue and "Option<String>" in issue for issue in issues), issues


def test_output_dir_consistency_flags_python_missing_validator() -> None:
    """Python 删 ``min_length=1`` —— CLI 直调可绕过前端门禁,需要 fail。"""
    module = _load_module()
    rust_text = "pub struct OutputConfig {\n    pub output_dir: Option<String>,\n}"
    py_text = (
        "class OutputConfig(_CamelBase):\n"
        "    output_dir: str | None\n"  # 没有 Field(default=None, min_length=1)
        "    open_on_complete: bool\n"
    )
    issues = module._diff_output_dir_optional_consistency(rust_text, py_text)
    assert any("Python" in issue and "min_length=1" in issue for issue in issues), issues


def test_error_code_wire_scan_allows_normalized_helpers() -> None:
    """Error envelopes may only pass code values through the wire normalizers."""
    module = _load_module()
    text = """
def emit(process_error, exc, pe):
    payload = {"type": "error", "code": error_code_to_wire(process_error.code)}
    payload2 = {"type": "error", "code": _wire_error_code(exc.code)}
    raise_error(error_code_to_wire(pe.code), pe.message)
    ProcessError(error_code_to_wire("TaskErrorCode.MISSING_MODEL"), "worker failed")
"""

    assert module._scan_python_error_code_wire_misuse("sample.py", text) == []


def test_error_code_wire_scan_flags_enum_repr_leaks() -> None:
    """Regression guard for ``TaskErrorCode.MISSING_MODEL`` leaking over NDJSON."""
    module = _load_module()
    text = """
def emit(process_error, exc, pe, event):
    payload = {"type": "error", "code": str(process_error.code)}
    payload2 = {"type": "error", "code": exc.code}
    raise_error(pe.code, pe.message)
    ProcessError(str(event.get("code") or "process_failed"), "worker failed")
"""

    issues = module._scan_python_error_code_wire_misuse("sample.py", text)

    assert len(issues) == 4
    assert any("dict['code']" in issue and "str(...code...)" in issue for issue in issues)
    assert any("dict['code']" in issue and "direct .code" in issue for issue in issues)
    assert any("raise_error" in issue and "direct .code" in issue for issue in issues)
    assert any("ProcessError" in issue and "str(...)" in issue for issue in issues)
