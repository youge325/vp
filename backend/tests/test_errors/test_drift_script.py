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
