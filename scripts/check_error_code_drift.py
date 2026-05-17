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

Phase 4.2 — 在硬验证 TaskErrorCode 之外,顺手扫描整个
``frontend/src/types/generated/`` 目录,把所有 ts-rs 派生的 string-enum
(形如 ``export type Foo = "a" | "b"``) 与 Rust 端对应 enum 的 variants
作交叉对比。任一 enum 出现漂移(TS 多 / TS 少)都会以 INFO 形式打到
stderr,但只 TaskErrorCode 的不一致会影响退出码 — 其它 enum 的 Python
侧目前是字面量散落,等 Phase 7 字面量收敛把它们也建成 enum class 后,
再把其加入硬验证列表。

退出码:
  0  TaskErrorCode 三处完全一致(其它 enum 漂移只在 stderr 报告)
  1  TaskErrorCode 发现漂移,stderr 输出 only-in-* 差集
  2  解析失败(文件缺失 / 正则不匹配 / 文件被裁剪)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST_TASK_PATH = ROOT / "frontend" / "src-tauri" / "src" / "models" / "task.rs"
RUST_CONFIG_PATH = ROOT / "frontend" / "src-tauri" / "src" / "models" / "config.rs"
RUST_PROTOCOL_PATH = ROOT / "frontend" / "src-tauri" / "src" / "protocol.rs"
PY_PATH = ROOT / "backend" / "app" / "errors" / "_codes.py"
TS_GENERATED_DIR = ROOT / "frontend" / "src" / "types" / "generated"
TS_TASK_ERROR_CODE_PATH = TS_GENERATED_DIR / "TaskErrorCode.ts"

# 注意:正则被特意写得"严"以拒绝畸形文件。
# Rust:  从 ``pub enum FooBar { ... }`` 块中提取 PascalCase variant 名;
#        按 ``#[serde(rename_all = "...")]`` 的语义本地转换。Phase D.3.5
#        删除了之前手维护的 ``as_str()`` 字符串映射(零调用方、易漂移),所以脚本
#        现在直接消费 enum 定义本身,不再需要 as_str() 同步。
_RUST_ENUM_HEADER_PATTERN = re.compile(
    r"#\[serde\(rename_all\s*=\s*\"(?P<rename>[a-z_-]+)\"\)\][^}]*?"
    r"pub\s+enum\s+(?P<name>[A-Z][A-Za-z0-9]+)\s*\{(?P<body>[^}]+)\}",
    re.DOTALL,
)
_RUST_VARIANT_PATTERN = re.compile(r"\b(?P<variant>[A-Z][A-Za-z0-9]+)\b")
# Python: ``CODE_NAME = "snake_case"``
_PY_MEMBER_PATTERN = re.compile(
    r"^\s+[A-Z_]+\s*=\s*\"(?P<code>[a-z_]+)\"",
    re.MULTILINE,
)
# TS:    union 字符串字面量:每一段 ``"snake_case"`` 用 ``|`` 串联
_TS_LITERAL_PATTERN = re.compile(r"\"(?P<code>[a-z0-9_-]+)\"")
_TS_UNION_HEADER_PATTERN = re.compile(
    r"export type (?P<name>[A-Z][A-Za-z0-9]+)\s*=\s*(?P<body>(?:\"[^\"]+\"\s*\|?\s*)+);",
)


def _pascal_to_snake(name: str) -> str:
    """Mirror ``#[serde(rename_all = "snake_case")]`` on PascalCase variants.

    Rust serde lower-cases each ASCII uppercase that follows a lowercase
    letter (or starts the identifier), inserting underscores between
    consecutive words. ``MissingFfmpeg`` -> ``missing_ffmpeg``,
    ``IoError`` -> ``io_error``.
    """
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def _pascal_to_kebab(name: str) -> str:
    """Mirror ``#[serde(rename_all = "kebab-case")]`` on PascalCase variants."""
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name).lower()


def _pascal_to_camel(name: str) -> str:
    """Mirror ``#[serde(rename_all = "camelCase")]`` on PascalCase variants."""
    if not name:
        return name
    return name[0].lower() + name[1:]


_RENAME_CONVERTERS: dict[str, callable] = {
    "snake_case": _pascal_to_snake,
    "kebab-case": _pascal_to_kebab,
    "camelCase": _pascal_to_camel,
}


def _fail_parse(message: str) -> None:
    sys.stderr.write(f"[check-error-code-drift] PARSE ERROR: {message}\n")
    sys.exit(2)


def _read(path: Path) -> str:
    if not path.exists():
        _fail_parse(f"file missing: {path}")
    return path.read_text(encoding="utf-8")


def _scan_rust_string_enums(text: str) -> dict[str, set[str]]:
    """Return ``{enum_name: {wire_values}}`` for every PascalCase enum with a rename_all attribute."""
    result: dict[str, set[str]] = {}
    for match in _RUST_ENUM_HEADER_PATTERN.finditer(text):
        rename = match.group("rename")
        converter = _RENAME_CONVERTERS.get(rename)
        if converter is None:
            continue  # unknown rename rule — skip rather than crash
        # Strip ``///`` doc comments before extracting variants — otherwise the
        # variant pattern would happily capture every PascalCase word in the
        # surrounding docs (``"The user pressed Cancel"`` → bogus variants).
        body_lines = [line for line in match.group("body").splitlines() if not line.lstrip().startswith("//")]
        body_clean = "\n".join(body_lines)
        variants = _RUST_VARIANT_PATTERN.findall(body_clean)
        result[match.group("name")] = {converter(v) for v in variants}
    return result


def _collect_rust_task_error_codes(text: str) -> set[str]:
    """从 ``pub enum TaskErrorCode { ... }`` 块提取变体名,本地 snake_case 化。

    Phase D.3.5:不再依赖 ``TaskErrorCode::as_str()`` 显式字符串表 — 该
    impl 已被删除,enum 上的 ``#[serde(rename_all = "snake_case")]`` 是
    wire 唯一可信源。脚本复刻这个转换以便离线校验三层一致性。
    """
    enums = _scan_rust_string_enums(text)
    codes = enums.get("TaskErrorCode")
    if not codes:
        _fail_parse(
            "could not locate `pub enum TaskErrorCode { ... }` block in task.rs; "
            "check whether the enum was renamed or moved",
        )
    return codes


def _collect_python_codes(text: str) -> set[str]:
    """从 ``TaskErrorCode(str, Enum)`` 类体提取 codes。"""
    codes = set(_PY_MEMBER_PATTERN.findall(text))
    if not codes:
        _fail_parse(
            'no `NAME = "code"` lines found in _codes.py; check whether the TaskErrorCode enum was restructured',
        )
    return codes


def _collect_ts_codes_from_task_error_code_file(text: str) -> set[str]:
    """从 ts-rs 生成的 TaskErrorCode union 字符串字面量集合提取 codes。"""
    union_lines = [line for line in text.splitlines() if " = " in line and "TaskErrorCode" in line]
    if not union_lines:
        _fail_parse("no `export type TaskErrorCode = ...` declaration found in TaskErrorCode.ts")
    codes = set(_TS_LITERAL_PATTERN.findall(union_lines[0]))
    if not codes:
        _fail_parse("TaskErrorCode union literal extracted no codes")
    return codes


def _scan_ts_string_enums(generated_dir: Path) -> dict[str, set[str]]:
    """Scan ``frontend/src/types/generated/*.ts`` for ``export type X = "a" | "b";`` unions.

    Returns ``{enum_name: {literals}}``. Files that contain only object types
    (no string-enum union) are silently skipped. Picks up every union that
    matches the pattern even when the alias name doesn't match the filename.
    """
    discovered: dict[str, set[str]] = {}
    for ts_file in sorted(generated_dir.glob("*.ts")):
        text = ts_file.read_text(encoding="utf-8")
        for match in _TS_UNION_HEADER_PATTERN.finditer(text):
            literals = set(_TS_LITERAL_PATTERN.findall(match.group("body")))
            if literals:
                discovered[match.group("name")] = literals
    return discovered


def _diff_task_error_code(rust: set[str], python: set[str], ts: set[str]) -> list[str]:
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


def _report_secondary_enum_drift(
    rust_enums: dict[str, set[str]],
    ts_enums: dict[str, set[str]],
) -> None:
    """Phase 4.2 — INFO-only Rust ↔ TS comparison for every other string-enum.

    These enums currently have no Python SSOT (their values are bare string
    literals scattered through the backend), so the script can only verify
    the Rust ↔ TS handshake. Any drift here is printed as INFO; it does not
    fail the check. Once Phase 7 collapses the FE/BE literals into named
    constants, the matching Python class can be added to the hard-check
    table below.
    """
    for name, rust_values in sorted(rust_enums.items()):
        if name == "TaskErrorCode":
            continue
        ts_values = ts_enums.get(name)
        if ts_values is None:
            sys.stderr.write(
                f"[check-error-code-drift] INFO: Rust enum {name} has no matching ts-rs export; "
                "skipped (does ts-rs derive include this enum?)\n",
            )
            continue
        only_rust = rust_values - ts_values
        only_ts = ts_values - rust_values
        if only_rust or only_ts:
            sys.stderr.write(
                f"[check-error-code-drift] INFO: {name} Rust ↔ TS drift "
                f"(only-in-rust={sorted(only_rust)}, only-in-ts={sorted(only_ts)})\n",
            )


def main() -> int:
    rust_task_text = _read(RUST_TASK_PATH)
    rust_config_text = _read(RUST_CONFIG_PATH)
    rust_protocol_text = _read(RUST_PROTOCOL_PATH)

    rust_task_codes = _collect_rust_task_error_codes(rust_task_text)
    python_codes = _collect_python_codes(_read(PY_PATH))
    ts_task_codes = _collect_ts_codes_from_task_error_code_file(_read(TS_TASK_ERROR_CODE_PATH))

    issues = _diff_task_error_code(rust_task_codes, python_codes, ts_task_codes)
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

    # INFO-only pass over the rest of the ts-rs string-enums.
    all_rust_enums: dict[str, set[str]] = {}
    for text in (rust_task_text, rust_config_text, rust_protocol_text):
        all_rust_enums.update(_scan_rust_string_enums(text))
    ts_enums = _scan_ts_string_enums(TS_GENERATED_DIR)
    _report_secondary_enum_drift(all_rust_enums, ts_enums)

    sys.stdout.write(
        f"[check-error-code-drift] OK ({len(rust_task_codes)} TaskErrorCode codes consistent across 3 layers; "
        f"scanned {len(all_rust_enums)} Rust enums, {len(ts_enums)} TS enums)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
