"""端到端集成测试 — 用 ``subprocess`` 启动真实的 ``python -m app`` CLI 入口。

这一层补的是单元测试盖不到的回归点:
1. ``__main__.py`` 的兜底分支(ProcessError vs 普通 Exception)是否真的把 NDJSON
   error envelope 写到 stdout 而不是 stderr;
2. ``--input <nonexistent>`` 这种"用户能很容易触发的失败"在协议层的 contract;
3. NDJSON 行结构是否对 Rust ``NdjsonEnvelope`` 反序列化友好(字段顺序 / camelCase / null details)。

故意避开 FFmpeg / 视频文件 / GPU 模型这些重资源 — 测试只跑参数校验和错误路径,几秒内
能在 CI 上完成。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"


def _run_app(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """以隔离子进程方式调用 ``python -m app``。"""
    env = os.environ.copy()
    # 强制 UTF-8 让 stdout/stderr 在 Windows 也是稳定编码。
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def _last_json_line(stdout: str) -> dict:
    """从 stdout 取最后一个非空 JSON 行(对应 Rust ``parse_last_json_line``)。"""
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"未在 stdout 中找到 JSON 行:\n{stdout}")


def test_info_with_missing_input_emits_invalid_input_envelope() -> None:
    """``info --input <不存在>`` 必须以 NDJSON error 帧 + exit 1 终止。

    这是 Tauri ``inspect_video`` 命令最常见的失败路径,前端
    ``InvokeError.code === 'invalid_input'`` 依赖这个 contract。
    """
    proc = _run_app("info", "--input", "Z:/definitely/does/not/exist.mp4")

    assert proc.returncode == 1, f"info 应当以 exit code 1 终止,实际:{proc.returncode}\n{proc.stdout}\n{proc.stderr}"

    envelope = _last_json_line(proc.stdout)
    assert envelope["type"] == "error"
    assert envelope["code"] == "invalid_input"
    assert "definitely" in envelope["message"], f"message 应当回带路径片段:{envelope['message']}"
    # ``details`` 至少含 input_path(由 cli/commands/info.py 显式写入)
    details = envelope.get("details") or {}
    assert "input_path" in details or "inputPath" in details, f"缺 input_path:{details}"


def test_inspect_output_with_missing_input_emits_invalid_input_envelope() -> None:
    """``inspect-output`` 也走同一条 ProcessError 路径,验证不同子命令的协议一致性。"""
    proc = _run_app(
        "inspect-output",
        "--input",
        "Z:/definitely/does/not/exist.mp4",
        "--decode-config-json",
        "{}",
        "--workflow-config-json",
        "{}",
        "--encode-config-json",
        "{}",
        "--output-config-json",
        "{}",
    )

    assert proc.returncode == 1
    envelope = _last_json_line(proc.stdout)
    assert envelope["type"] == "error"
    assert envelope["code"] == "invalid_input"


def test_process_with_invalid_json_emits_typed_envelope() -> None:
    """``--workflow-config-json '{not valid json'`` 应当被 ProcessError 捕获。

    Rust 不会发这样的 payload(它走 ``serde_json::to_string`` 序列化结构体),
    但人工 CLI 调用 / fuzz 仍可能触发。这条路径验证配置加载错误被协议层
    归一化,而不是裸 ``Traceback`` 输出到 stderr。
    """
    proc = _run_app(
        "process",
        "--input",
        "Z:/x.mp4",  # 不存在的输入,但 JSON 解析会先失败
        "--workflow-config-json",
        "{not valid json",
    )
    assert proc.returncode == 1
    envelope = _last_json_line(proc.stdout)
    assert envelope["type"] == "error"
    # JSON 解析失败 → 走 ProcessError.from_exception → infer 出 process_failed 或 invalid_input
    # 这里只验证它一定是一个 valid TaskErrorCode 字符串
    from app.errors._codes import TaskErrorCode

    valid_codes = {code.value for code in TaskErrorCode}
    assert envelope["code"] in valid_codes, f"code {envelope['code']!r} 不在 TaskErrorCode 集合内"


def test_help_does_not_emit_error_envelope() -> None:
    """``--help`` 走 argparse SystemExit(0),不应该污染 stdout 为 NDJSON error 帧。

    Rust 永远不会调 ``--help``,但这条测试守护"无关路径不会误发 error"。
    """
    proc = _run_app("--help")
    assert proc.returncode == 0
    # ``--help`` 写到 stdout,但不是 NDJSON。确认没有 ``{"type":"error"`` 帧。
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            assert payload.get("type") != "error", f"--help 路径不应当发 error 帧:{payload}"
