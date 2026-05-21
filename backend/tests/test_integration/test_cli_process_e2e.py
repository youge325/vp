"""端到端 smoke 测试 — 覆盖 CLI → FFmpeg → NDJSON 完整数据流。

与 ``test_cli_envelope_e2e.py`` 的区别:
- 信封测试只跑错误路径(不依赖 FFmpeg/视频),几秒完成;
- 本文件跑真实处理流程,验证 config 解析 → FFmpeg 调用 → 输出文件
  的完整性。需要 FFmpeg 和一个测试视频(由 CI 或本地预先生成)。

通过环境变量接收外部输入,让同一套测试既能在 CI 上跑,
也能在本地开发者机器上跑(只需提前生成测试视频):
  VP_E2E_INPUT      — 测试视频路径(默认: /tmp/vp-e2e-test.mp4)
  VP_E2E_OUTPUT_DIR — 输出目录(默认: /tmp/vp-e2e-output)
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

_default_input = "/tmp/vp-e2e-test.mp4" if sys.platform != "win32" else r"C:\tmp\vp-e2e-test.mp4"
_default_output = "/tmp/vp-e2e-output" if sys.platform != "win32" else r"C:\tmp\vp-e2e-output"
E2E_INPUT = os.environ.get("VP_E2E_INPUT", _default_input)
E2E_OUTPUT_DIR = os.environ.get("VP_E2E_OUTPUT_DIR", _default_output)


def _run_app(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """以隔离子进程方式调用 ``python -m app``。

    自动为每次调用分配独立日志目录(VP_LOG_DIR),避免 Windows 上
    前后两次 subprocess 间隔过短时日志文件句柄未释放导致的
    PermissionError([WinError 32])。
    """
    import tempfile

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 隔离日志目录,避免多进程文件锁冲突
    env["VP_LOG_DIR"] = tempfile.mkdtemp(prefix="vp-e2e-logs-")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def _last_json_line(stdout: str) -> dict:
    """从 stdout 取最后一个非空 JSON 行。"""
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"未在 stdout 中找到 JSON 行:\n{stdout}")


def _all_json_lines(stdout: str) -> list[dict]:
    """提取 stdout 中所有 JSON 行(按出现顺序)。"""
    result: list[dict] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            result.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return result


@pytest.fixture
def e2e_input() -> str:
    path = Path(E2E_INPUT)
    if not path.exists():
        pytest.skip(f"测试视频不存在: {path} — 请先运行 ffmpeg 生成 synthetic 视频")
    return str(path.resolve())


@pytest.fixture
def e2e_output_dir() -> str:
    path = Path(E2E_OUTPUT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


@pytest.fixture(autouse=True)
def _cleanup_output(e2e_output_dir: str) -> None:
    """每个测试前清理输出目录,避免上次运行的残留影响当前测试。"""
    out_dir = Path(e2e_output_dir)
    for f in out_dir.glob("*"):
        if f.is_file():
            f.unlink()


class TestCheckCommand:
    """验证 ``python -m app check`` 的 NDJSON 输出完整性。"""

    def test_check_emits_valid_ndjson(self) -> None:
        proc = _run_app("check")
        assert proc.returncode == 0, f"check 应当以 0 退出:\n{proc.stderr}"

        lines = _all_json_lines(proc.stdout)
        assert len(lines) >= 1, "check 应至少输出一行 NDJSON"

        envelope = lines[0]
        assert envelope.get("type") == "check"
        assert "ffmpeg" in envelope, "check 输出应含 ffmpeg 字段"
        assert "resources" in envelope, "check 输出应含 resources 字段"

    def test_check_includes_tensor_backends(self) -> None:
        proc = _run_app("check")
        envelope = _last_json_line(proc.stdout)
        dev_support = envelope.get("backendDeviceSupport", {})
        # 至少应返回 pytorch / paddle / onnx 三个 key,
        # 值可以为 false(未安装),但结构必须存在。
        assert "pytorch" in dev_support
        assert "paddle" in dev_support
        assert "onnx" in dev_support


class TestInfoCommand:
    """验证 ``python -m app info`` 能正确解析真实视频。"""

    def test_info_emits_video_metadata(self, e2e_input: str) -> None:
        proc = _run_app("info", "--input", e2e_input)
        assert proc.returncode == 0, f"info 失败:\n{proc.stderr}"

        envelope = _last_json_line(proc.stdout)
        assert envelope.get("type") == "info"
        assert envelope.get("frames", 0) > 0, "frame count 应 > 0"
        assert envelope.get("fps", 0) > 0, "fps 应 > 0"
        assert envelope.get("duration", 0) >= 0, "duration 应 >= 0"
        assert envelope.get("width", 0) > 0, "width 应 > 0"
        assert envelope.get("height", 0) > 0, "height 应 > 0"
        assert envelope.get("videoCodec"), "videoCodec 不应为空"


class TestProcessFormatConversion:
    """验证最轻量的 format_conversion 完整流程。"""

    def test_process_format_conversion_completes(self, e2e_input: str, e2e_output_dir: str) -> None:
        proc = _run_app(
            "process",
            "--input",
            e2e_input,
            "--output-dir",
            e2e_output_dir,
            "--algorithm",
            "format_conversion",
            "--codec",
            "h264",
        )
        assert proc.returncode == 0, f"process 失败:\n{proc.stderr}\n{proc.stdout}"

        lines = _all_json_lines(proc.stdout)
        assert len(lines) >= 2, "应至少输出 progress + completed 两帧"

        # 验证最后一帧是 completed
        completed = lines[-1]
        assert completed.get("type") == "completed"
        output_path = completed.get("outputPath")
        assert output_path, "completed 帧应含 outputPath"
        assert completed.get("processedFrames", 0) > 0, "processedFrames 应 > 0"
        assert completed.get("timeSeconds", 0) >= 0, "timeSeconds 应 >= 0"

        # 验证文件实际存在且非空
        assert Path(output_path).exists(), f"输出文件不存在: {output_path}"
        assert Path(output_path).stat().st_size > 0, f"输出文件为空: {output_path}"

    def test_process_resume_conflict_on_second_run(self, e2e_input: str, e2e_output_dir: str) -> None:
        # 先跑一次,生成输出文件
        first = _run_app(
            "process",
            "--input",
            e2e_input,
            "--output-dir",
            e2e_output_dir,
            "--algorithm",
            "format_conversion",
            "--codec",
            "h264",
        )
        assert first.returncode == 0, "第一次 process 应成功"

        # 同一输入再跑一次,应触发 resume_conflict
        second = _run_app(
            "process",
            "--input",
            e2e_input,
            "--output-dir",
            e2e_output_dir,
            "--algorithm",
            "format_conversion",
            "--codec",
            "h264",
        )
        assert second.returncode != 0, "第二次 process 应以非 0 退出"

        envelope = _last_json_line(second.stdout)
        assert envelope.get("type") == "error"
        assert envelope.get("code") == "resume_conflict"

        details = envelope.get("details") or {}
        assert "outputPath" in details, "details 应含 outputPath"
        assert "completedChunks" in details, "details 应含 completedChunks"
        assert "completedOutputFrames" in details, "details 应含 completedOutputFrames"
        assert "sidecarSignatureMatch" in details, "details 应含 sidecarSignatureMatch"
        assert "input_path" in details, "details 应含 input_path(由 process.py 注入)"

    def test_process_without_explicit_defaults_uses_settings(self, e2e_input: str, e2e_output_dir: str) -> None:
        """不传 --multi/--scale/--fp16,验证默认值从 settings 正确穿透。

        format_conversion 本身不消费这些值,但 parser 必须接受缺失,
        且 defaults.py 的 _default_workflow_config 应在 args.X is None
        时回退到 settings.RIFE_*。
        """
        proc = _run_app(
            "process",
            "--input",
            e2e_input,
            "--output-dir",
            e2e_output_dir,
            "--algorithm",
            "format_conversion",
            "--codec",
            "h264",
            # 故意不传 --multi --scale --fp16
        )
        assert proc.returncode == 0, f"不传默认值时应仍能成功:\n{proc.stderr}\n{proc.stdout}"

        envelope = _last_json_line(proc.stdout)
        assert envelope.get("type") == "completed"
