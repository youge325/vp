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

Phase 9 — NdjsonEnvelope ↔ NdjsonEventType 跨语言契约硬化。
Python ``NdjsonEventType`` 是 Python emit 的全集(stream 长任务 + oneshot
命令);Rust ``NdjsonEnvelope`` 只覆盖 stream 长任务路径上 ``readers.rs``
要解码的事件。允许 Python 端有 ``NDJSON_ONESHOT_WHITELIST`` 中的事件,
其余必须双向匹配,否则任何一侧加新事件而另一侧没跟上时,就会触发漂移
失败(退出 1)。

退出码:
  0  TaskErrorCode 三处一致,且 NdjsonEnvelope ↔ NdjsonEventType 漂移
     ≤ ``NDJSON_ONESHOT_WHITELIST``(其它 enum 漂移只在 stderr 报告)
  1  TaskErrorCode 漂移 或 NdjsonEnvelope/NdjsonEventType 漂移
  2  解析失败(文件缺失 / 正则不匹配 / 文件被裁剪)
"""

from __future__ import annotations

import ast
import re
import sys
import warnings
from pathlib import Path

# Force UTF-8 on stdout/stderr so Chinese fix-it tips & arrow glyphs (↔)
# survive on Windows consoles whose default cp936 codepage can't encode
# them. cargo's build.rs already sets PYTHONIOENCODING=utf-8 explicitly,
# but pre-commit / direct ``python scripts/...`` invocations don't.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RUST_TASK_PATH = ROOT / "frontend" / "src-tauri" / "src" / "models" / "task.rs"
RUST_CONFIG_PATH = ROOT / "frontend" / "src-tauri" / "src" / "models" / "config.rs"
RUST_PROTOCOL_PATH = ROOT / "frontend" / "src-tauri" / "src" / "protocol.rs"
RUST_ENVELOPE_PATH = ROOT / "frontend" / "src-tauri" / "src" / "tasks" / "envelope.rs"
PY_PATH = ROOT / "backend" / "app" / "errors" / "_codes.py"
PY_PROTOCOL_PATH = ROOT / "backend" / "app" / "protocol" / "__init__.py"
PY_MODELS_PATH = ROOT / "backend" / "app" / "models" / "__init__.py"
BACKEND_APP_DIR = ROOT / "backend" / "app"
TS_GENERATED_DIR = ROOT / "frontend" / "src" / "types" / "generated"
TS_TASK_ERROR_CODE_PATH = TS_GENERATED_DIR / "TaskErrorCode.ts"

# Phase 9 — Python emits these via ``oneshot`` CLI commands (info /
# check / inspect-output). Their stdout is read by
# ``frontend/src-tauri/src/tasks/oneshot.rs::parse_last_json_line`` as a
# generic ``serde_json::Value`` — i.e. they intentionally do NOT need
# corresponding ``NdjsonEnvelope`` variants. The drift checker subtracts
# this set from the Python-only diff before failing, so adding a NEW
# wire-name on either side without updating the other still fails fast.
NDJSON_ONESHOT_WHITELIST = frozenset({"info", "check", "resume_inspection"})

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
# TS:    union 字符串字面量:每一段 ``"snake_case"`` 用 ``|`` 串联。
#        这里避免用单个大正则吞完整 union,防止畸形输入触发回溯放大。
_TS_TYPE_NAME_PATTERN = re.compile(r"[A-Z][A-Za-z0-9]+")
_TS_UNION_LITERAL_PATTERN = re.compile(r"\"(?P<code>[a-z0-9_-]+)\"")

# Phase 9 — Python ``class NdjsonEventType(str, Enum):`` block. Anchored on
# the class name so we don't confuse it with ``class TaskErrorCode``.
_PY_NDJSON_EVENT_TYPE_BLOCK = re.compile(
    r"class NdjsonEventType\(\s*str\s*,\s*Enum\s*\):\s*\n"
    r"(?P<body>(?:[ \t]+[A-Z_]+\s*=\s*\"[a-z_]+\"\s*\n)+)",
)
_PY_NDJSON_MEMBER_PATTERN = re.compile(
    r"^[ \t]+[A-Z_]+\s*=\s*\"(?P<wire>[a-z_]+)\"",
    re.MULTILINE,
)
# Rust ``pub enum NdjsonEnvelope { ... }`` block. Each variant carries an
# explicit ``#[serde(rename = "...")]`` attribute so we collect those
# directly rather than reapplying the top-level ``rename_all`` rule.
_RUST_NDJSON_ENVELOPE_BLOCK = re.compile(
    r"pub\s+enum\s+NdjsonEnvelope\s*\{(?P<body>[^}]+)\}",
    re.DOTALL,
)
_RUST_NDJSON_VARIANT_RENAME_PATTERN = re.compile(
    r"#\[serde\(rename\s*=\s*\"(?P<wire>[a-z_]+)\"\)\]",
)
_ERROR_CODE_WRAPPER_CALL_NAMES = {"ProcessError", "raise_error"}


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
    for statement in text.split(";"):
        parsed = _parse_ts_string_union_export(statement)
        if parsed and parsed[0] == "TaskErrorCode":
            return parsed[1]
    _fail_parse("no `export type TaskErrorCode = ...` declaration found in TaskErrorCode.ts")


def _parse_ts_string_union_export(statement: str) -> tuple[str, set[str]] | None:
    """Parse one ``export type Foo = "a" | "b"`` statement without a backtracking regex."""
    prefix = "export type "
    export_start = statement.find(prefix)
    if export_start < 0:
        return None
    stripped = statement[export_start:].strip()
    name_part, separator, body = stripped[len(prefix) :].partition("=")
    if separator != "=":
        return None
    name = name_part.strip()
    if not _TS_TYPE_NAME_PATTERN.fullmatch(name):
        return None
    literals: set[str] = set()
    for member in body.split("|"):
        match = _TS_UNION_LITERAL_PATTERN.fullmatch(member.strip())
        if not match:
            return None
        literals.add(match.group("code"))
    return (name, literals) if literals else None


def _collect_python_ndjson_event_types(text: str) -> set[str]:
    """从 ``class NdjsonEventType(str, Enum)`` 类体提取 wire values。"""
    block_match = _PY_NDJSON_EVENT_TYPE_BLOCK.search(text)
    if not block_match:
        _fail_parse(
            "could not locate `class NdjsonEventType(str, Enum):` block in protocol/__init__.py; "
            "check whether the class was renamed or moved",
        )
    wires = set(_PY_NDJSON_MEMBER_PATTERN.findall(block_match.group("body")))
    if not wires:
        _fail_parse('NdjsonEventType class body matched but no `NAME = "wire"` members extracted')
    return wires


def _collect_rust_envelope_wire_names(text: str) -> set[str]:
    """从 ``pub enum NdjsonEnvelope { ... }`` 块提取 ``#[serde(rename)]`` wire 名集合。"""
    block_match = _RUST_NDJSON_ENVELOPE_BLOCK.search(text)
    if not block_match:
        _fail_parse(
            "could not locate `pub enum NdjsonEnvelope { ... }` block in tasks/envelope.rs; "
            "check whether the enum was renamed or moved",
        )
    wires = set(_RUST_NDJSON_VARIANT_RENAME_PATTERN.findall(block_match.group("body")))
    if not wires:
        _fail_parse(
            'NdjsonEnvelope block matched but no `#[serde(rename = "...")]` attributes extracted; '
            "did serde tagging style change?",
        )
    return wires


def _diff_ndjson_event_types(python: set[str], rust_envelope: set[str]) -> list[str]:
    """Compare Python ``NdjsonEventType`` against Rust ``NdjsonEnvelope`` variants.

    Rule:
    - Every Rust variant wire-name MUST exist in Python (Rust can't decode
      events Python doesn't declare).
    - Python may legitimately have **extra** wire-names — but only the ones
      in ``NDJSON_ONESHOT_WHITELIST``. Anything else means the two sides
      drifted: either someone added a Python event without wiring Rust, or
      removed an event from the whitelist without updating it here.
    """
    issues: list[str] = []
    rust_only = rust_envelope - python
    if rust_only:
        issues.append(
            f"Rust NdjsonEnvelope ↔ Python NdjsonEventType 漂移: "
            f"only-in-rust={sorted(rust_only)} (Rust 端的 variant 在 Python 端缺失,"
            "后端 emit 时不会出现此 wire 名,readers.rs 永远不会命中此分支)",
        )
    python_only = python - rust_envelope
    unexpected = python_only - NDJSON_ONESHOT_WHITELIST
    missing_whitelist = NDJSON_ONESHOT_WHITELIST - python_only
    if unexpected:
        issues.append(
            f"Python NdjsonEventType 有未授权的 oneshot-only 事件,Rust 端不识别: "
            f"only-in-python(unexpected)={sorted(unexpected)}; "
            "请把它加入 NdjsonEnvelope(并配套 readers.rs 路由),"
            "或加入 scripts/check_error_code_drift.py 的 NDJSON_ONESHOT_WHITELIST",
        )
    if missing_whitelist:
        issues.append(
            f"白名单 NDJSON_ONESHOT_WHITELIST 中的事件不再出现在 Python NdjsonEventType: "
            f"{sorted(missing_whitelist)};请同步删除白名单条目",
        )
    return issues


def _scan_ts_string_enums(generated_dir: Path) -> dict[str, set[str]]:
    """Scan ``frontend/src/types/generated/*.ts`` for ``export type X = "a" | "b";`` unions.

    Returns ``{enum_name: {literals}}``. Files that contain only object types
    (no string-enum union) are silently skipped. Picks up every union that
    matches the pattern even when the alias name doesn't match the filename.
    """
    discovered: dict[str, set[str]] = {}
    for ts_file in sorted(generated_dir.glob("*.ts")):
        text = ts_file.read_text(encoding="utf-8")
        for statement in text.split(";"):
            parsed = _parse_ts_string_union_export(statement)
            if parsed:
                discovered[parsed[0]] = parsed[1]
    return discovered


def _diff_output_dir_optional_consistency(rust_config_text: str, py_models_text: str) -> list[str]:
    """Phase 18 — outputDir 三层必填一致性硬验证。

    Rust ``OutputConfig.output_dir`` 必须是 ``Option<String>``(允许 null
    wire 表达"未选"),Python ``OutputConfig.output_dir`` 必须有
    ``min_length=1`` 字段约束(拒空串/纯空白)。任一方向漂移就 fail-loudly:
    - Rust 退回 ``String``:wire 上空串无法被 type 表达"未选",前端可能误传
      ``""`` 让 Python validator 处理(行为虽仍 fail,但语义不清晰)
    - Python 删 ``min_length=1`` validator:CLI 直调 / 测试可绕过前端门禁,
      空 outputDir 走到 commands 里 ``output_config["outputDir"]`` 拿到空串,
      ``Path("").mkdir()`` 行为不定
    """
    issues: list[str] = []
    rust_pattern = re.compile(
        r"pub struct OutputConfig\s*\{[^}]*?pub output_dir:\s*Option<String>",
        re.DOTALL,
    )
    if not rust_pattern.search(rust_config_text):
        issues.append(
            "Phase 18 outputDir drift: Rust models/config.rs OutputConfig.output_dir "
            '必须是 Option<String>(允许 null wire 表达"未选")'
        )
    # Phase 2.1 修正 — Python 同步为 ``str | None = Field(default=None, min_length=1)``,
    # 与 Rust ``Option<String>`` 保持 schema 一致。wire 上的 ``null`` 被 Pydantic
    # 接受后再由 validator 在业务层 fail-loudly,避免反序列化时抛晦涩的
    # ``ValidationError``。
    py_pattern = re.compile(
        r"class OutputConfig\([^)]*\):[\s\S]*?output_dir:\s*(?:str\s*\|\s*None|Optional\[str\])\s*=\s*Field\(default=None,\s*min_length=1",
        re.DOTALL,
    )
    if not py_pattern.search(py_models_text):
        issues.append(
            "Phase 18 outputDir drift: Python models OutputConfig.output_dir "
            "必须是 str | None = Field(default=None, min_length=1) "
            "(与 Rust Option<String> 同步,validator 拒空串/空白)"
        )
    return issues


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _contains_code_attribute(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Attribute) and child.attr == "code" for child in ast.walk(node))


def _wire_normalizer_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    name = _call_name(node.func)
    if name in {"error_code_to_wire", "_wire_error_code"}:
        return name
    return None


def _describe_forbidden_wire_code_expr(node: ast.AST) -> str | None:
    if _wire_normalizer_name(node):
        return None
    if isinstance(node, ast.Call) and _call_name(node.func) == "str":
        return "str(...code...)" if _contains_code_attribute(node) else "str(...)"
    if isinstance(node, ast.Attribute) and node.attr == "code":
        return "direct .code"
    return None


def _scan_python_error_code_wire_misuse(filename: str, text: str) -> list[str]:
    """Find Python code paths that can leak enum reprs over the NDJSON wire."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text, filename=filename)
    except SyntaxError as exc:
        _fail_parse(f"could not parse Python source for error-code wire scan: {filename}: {exc}")

    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=False):
                if not isinstance(key, ast.Constant) or key.value != "code":
                    continue
                problem = _describe_forbidden_wire_code_expr(value)
                if problem:
                    issues.append(
                        f"{filename}:{value.lineno}: dict['code'] uses {problem}; "
                        "wrap task error codes with error_code_to_wire(...) or _wire_error_code(...)",
                    )
            continue

        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name not in _ERROR_CODE_WRAPPER_CALL_NAMES or not node.args:
                continue
            problem = _describe_forbidden_wire_code_expr(node.args[0])
            if problem:
                issues.append(
                    f"{filename}:{node.args[0].lineno}: {name}(...) first code argument uses {problem}; "
                    "wrap task error codes with error_code_to_wire(...)",
                )
    return issues


def _scan_backend_error_code_wire_misuse() -> list[str]:
    issues: list[str] = []
    for path in sorted(BACKEND_APP_DIR.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        issues.extend(_scan_python_error_code_wire_misuse(rel, _read(path)))
    return issues


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
    rust_envelope_text = _read(RUST_ENVELOPE_PATH)
    py_protocol_text = _read(PY_PROTOCOL_PATH)
    py_models_text = _read(PY_MODELS_PATH)

    rust_task_codes = _collect_rust_task_error_codes(rust_task_text)
    python_codes = _collect_python_codes(_read(PY_PATH))
    ts_task_codes = _collect_ts_codes_from_task_error_code_file(_read(TS_TASK_ERROR_CODE_PATH))

    issues = _diff_task_error_code(rust_task_codes, python_codes, ts_task_codes)

    # Phase 9 — hard-verify the NdjsonEnvelope ↔ NdjsonEventType handshake.
    py_ndjson_events = _collect_python_ndjson_event_types(py_protocol_text)
    rust_envelope_wires = _collect_rust_envelope_wire_names(rust_envelope_text)
    ndjson_issues = _diff_ndjson_event_types(py_ndjson_events, rust_envelope_wires)
    issues.extend(ndjson_issues)

    # Phase 18 — outputDir 三层必填一致性。
    output_dir_issues = _diff_output_dir_optional_consistency(rust_config_text, py_models_text)
    issues.extend(output_dir_issues)

    # PaddleGAN stage-worker regression — any Python error envelope crossing
    # into Rust must serialize enum codes through the wire normalizers.
    issues.extend(_scan_backend_error_code_wire_misuse())

    if issues:
        sys.stderr.write("[check-error-code-drift] DRIFT DETECTED:\n")
        for issue in issues:
            sys.stderr.write(f"  - {issue}\n")
        sys.stderr.write(
            "\n修复建议:\n"
            "  1. 三处都补齐缺失的 code\n"
            "  2. 在 src-tauri/ 跑 `cargo test --quiet` 重新生成 ts-rs 文件\n"
            "  3. 在 backend/ 跑 `python -m pytest tests/test_errors -q` 验证 round-trip\n"
            "  4. 若新增了 oneshot-only NDJSON 事件,把 wire 名加入脚本顶部的 NDJSON_ONESHOT_WHITELIST\n",
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
        f"NdjsonEnvelope ↔ NdjsonEventType handshake verified "
        f"({len(rust_envelope_wires)} stream variants + {len(py_ndjson_events) - len(rust_envelope_wires)} oneshot-only); "
        f"OutputConfig.outputDir Phase 18 contract verified (Rust Option<String> ↔ Python min_length=1); "
        f"scanned {len(all_rust_enums)} Rust enums, {len(ts_enums)} TS enums)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
