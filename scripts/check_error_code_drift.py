#!/usr/bin/env python3
"""TaskErrorCode 三层一致性检查脚本(pre-commit / CI 入口)。

VP Workbench 的错误码在 Rust / Python / TypeScript 三处都有定义。
即便 ts-rs 把 Rust enum 自动派生到 TS,生成步骤一旦遗漏(忘 ``cargo test`` 重新生成)
或某一侧手工修改,就会出现漂移。本脚本独立于 pytest 运行,把检查时机前移到 git commit,
让漂移在最早期被拦下。

SSOT:
  Rust:   frontend/src-tauri/src/models/task.rs        :: enum TaskErrorCode
  Python: backend/app/errors/_codes.py                 :: class TaskErrorCode
  TS:     frontend/src/types/generated/TaskErrorCode.ts:: type TaskErrorCode (ts-rs 派生)

退出码:
  0  三处完全一致
  1  发现漂移,stderr 输出 only-in-* 差集
  2  解析失败(文件缺失 / 正则不匹配 / 文件被裁剪)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST_PATH = ROOT / "frontend" / "src-tauri" / "src" / "models" / "task.rs"
PY_PATH = ROOT / "backend" / "app" / "errors" / "_codes.py"
TS_PATH = ROOT / "frontend" / "src" / "types" / "generated" / "TaskErrorCode.ts"

# 注意:正则被特意写得"严"以拒绝畸形文件。
# Rust:  从 ``pub enum TaskErrorCode { ... }`` 块中提取 PascalCase variant 名,
#        再按 ``#[serde(rename_all = "snake_case")]`` 的语义本地转换。Phase D.3.5
#        删除了之前手维护的 ``as_str()`` 字符串映射(零调用方、易漂移),所以脚本
#        现在直接消费 enum 定义本身,不再需要 as_str() 同步。
_RUST_ENUM_BLOCK_PATTERN = re.compile(
    r"pub\s+enum\s+TaskErrorCode\s*\{(?P<body>[^}]+)\}",
    re.DOTALL,
)
_RUST_VARIANT_PATTERN = re.compile(r"\b(?P<variant>[A-Z][A-Za-z0-9]+)\b")
# Python: ``CODE_NAME = "snake_case"``
_PY_MEMBER_PATTERN = re.compile(
    r"^\s+[A-Z_]+\s*=\s*\"(?P<code>[a-z_]+)\"",
    re.MULTILINE,
)
# TS:    union 字符串字面量:每一段 ``"snake_case"`` 用 ``|`` 串联
_TS_LITERAL_PATTERN = re.compile(r"\"(?P<code>[a-z_]+)\"")


def _pascal_to_snake(name: str) -> str:
    """Mirror ``#[serde(rename_all = "snake_case")]`` on PascalCase variants.

    Rust serde lower-cases each ASCII uppercase that follows a lowercase
    letter (or starts the identifier), inserting underscores between
    consecutive words. ``MissingFfmpeg`` -> ``missing_ffmpeg``,
    ``IoError`` -> ``io_error``.
    """
    # Insert ``_`` before any uppercase preceded by a lowercase letter.
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def _fail_parse(message: str) -> None:
    sys.stderr.write(f"[check-error-code-drift] PARSE ERROR: {message}\n")
    sys.exit(2)


def _read(path: Path) -> str:
    if not path.exists():
        _fail_parse(f"file missing: {path}")
    return path.read_text(encoding="utf-8")


def collect_rust_codes(text: str) -> set[str]:
    """从 ``pub enum TaskErrorCode { ... }`` 块提取变体名,本地 snake_case 化。

    Phase D.3.5:不再依赖 ``TaskErrorCode::as_str()`` 显式字符串表 — 该
    impl 已被删除,enum 上的 ``#[serde(rename_all = "snake_case")]`` 是
    wire 唯一可信源。脚本复刻这个转换以便离线校验三层一致性。
    """
    block_match = _RUST_ENUM_BLOCK_PATTERN.search(text)
    if not block_match:
        _fail_parse(
            "could not locate `pub enum TaskErrorCode { ... }` block in task.rs; "
            "check whether the enum was renamed or moved",
        )
    body = block_match.group("body")
    variants = _RUST_VARIANT_PATTERN.findall(body)
    if not variants:
        _fail_parse(
            "no PascalCase variants found inside the TaskErrorCode enum body",
        )
    return {_pascal_to_snake(variant) for variant in variants}


def collect_python_codes(text: str) -> set[str]:
    """从 ``TaskErrorCode(str, Enum)`` 类体提取 codes。"""
    codes = set(_PY_MEMBER_PATTERN.findall(text))
    if not codes:
        _fail_parse(
            'no `NAME = "code"` lines found in _codes.py; check whether the TaskErrorCode enum was restructured',
        )
    return codes


def collect_ts_codes(text: str) -> set[str]:
    """从 ts-rs 生成的 union 字符串字面量集合提取 codes。

    生成文件形如:
        export type TaskErrorCode = "missing_ffmpeg" | "missing_model" | ...;
    """
    # 跳过开头注释里可能出现的 URL 字面量,只看含 "= " 的那一行
    union_lines = [line for line in text.splitlines() if " = " in line and "TaskErrorCode" in line]
    if not union_lines:
        _fail_parse("no `export type TaskErrorCode = ...` declaration found in TaskErrorCode.ts")
    codes = set(_TS_LITERAL_PATTERN.findall(union_lines[0]))
    if not codes:
        _fail_parse("TaskErrorCode union literal extracted no codes")
    return codes


def diff_report(rust: set[str], python: set[str], ts: set[str]) -> list[str]:
    issues: list[str] = []
    only_rust = rust - python
    only_python = python - rust
    if only_rust or only_python:
        issues.append(
            f"Rust ↔ Python 漂移: only-in-rust={sorted(only_rust)}, only-in-python={sorted(only_python)}",
        )
    only_rust_ts = rust - ts
    only_ts = ts - rust
    if only_rust_ts or only_ts:
        issues.append(
            "Rust ↔ TS 漂移(可能未重新跑 cargo test 生成 ts-rs 文件):"
            f" only-in-rust={sorted(only_rust_ts)}, only-in-ts={sorted(only_ts)}",
        )
    only_python_ts = python - ts
    only_ts_python = ts - python
    if only_python_ts or only_ts_python:
        issues.append(
            f"Python ↔ TS 漂移: only-in-python={sorted(only_python_ts)}, only-in-ts={sorted(only_ts_python)}",
        )
    return issues


def main() -> int:
    rust = collect_rust_codes(_read(RUST_PATH))
    python = collect_python_codes(_read(PY_PATH))
    ts = collect_ts_codes(_read(TS_PATH))

    issues = diff_report(rust, python, ts)
    if issues:
        sys.stderr.write("[check-error-code-drift] DRIFT DETECTED:\n")
        for issue in issues:
            sys.stderr.write(f"  - {issue}\n")
        sys.stderr.write(
            "\n修复建议:\n"
            "  1. 三处都补齐缺失的 code\n"
            "  2. 在 src-tauri/ 跑 `cargo test --quiet` 重新生成 ts-rs 文件\n"
            "  3. 在 backend/ 跑 `python -m pytest tests/test_errors -q` 验证 round-trip\n",
        )
        return 1

    sys.stdout.write(f"[check-error-code-drift] OK ({len(rust)} codes consistent across 3 layers)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
