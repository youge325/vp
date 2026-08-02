from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def run_python_probe(code: str, *, timeout: int = 60) -> None:
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, (
        f"Required runtime probe failed.\ncode:\n{code}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def require_python_module(module_name: str) -> None:
    run_python_probe(f"import {module_name}")


def require_paddle_cuda() -> None:
    run_python_probe("import paddle; raise SystemExit(0 if paddle.device.is_compiled_with_cuda() else 1)")


def generate_input_video(
    path: Path,
    *,
    width: int,
    height: int,
    num_frames: int,
    rate: int,
    duration: float,
    with_audio: bool = False,
) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration}:size={width}x{height}:rate={rate}",
    ]
    if with_audio:
        command.extend(["-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}"])
    command.extend(["-frames:v", str(num_frames), "-pix_fmt", "yuv420p"])
    if with_audio:
        command.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-shortest"])
    else:
        command.append("-an")
    command.extend([str(path), "-y"])
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"Failed to generate e2e input video:\n{result.stderr}"
    assert_nonempty_file(path, "generated e2e input video")


def run_app(
    *args: str,
    stdin_json: dict[str, Any] | None = None,
    extra_env: dict[str, str] | None = None,
    timeout: int = 900,
    log_prefix: str = "vp-full-e2e-logs-",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "VP_LOG_DIR": tempfile.mkdtemp(prefix=log_prefix),
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        cwd=BACKEND_DIR,
        env=env,
        input=json.dumps(stdin_json) if stdin_json is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )


def json_lines(stdout: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def last_json_line(stdout: str) -> dict[str, Any]:
    payload = try_last_json_line(stdout)
    assert payload is not None, f"No JSON lines found in stdout:\n{stdout}"
    return payload


def try_last_json_line(stdout: str) -> dict[str, Any] | None:
    payloads = json_lines(stdout)
    return payloads[-1] if payloads else None


def trace_lines(path: Path) -> list[dict[str, Any]]:
    assert path.is_file(), f"PP-MSVSR trace file was not written: {path}"
    payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert payloads, f"PP-MSVSR trace file was empty: {path}"
    return payloads


def make_paddlegan_process_config(
    output_dir: Path,
    *,
    engine: str,
    num_frames: int,
    interpolation_enabled: bool = False,
    segment_frames: int | None = None,
) -> dict[str, Any]:
    return {
        "decode": {
            "mode": "software",
            "hwaccel": "",
            "hwaccelDevice": None,
            "decoder": "software",
            "options": {},
        },
        "workflow": {
            "fpsMode": "multi",
            "processOrder": (
                "frame_interpolation_then_super_resolution"
                if interpolation_enabled
                else "super_resolution_then_interpolation"
            ),
            "interpolation": {
                "enabled": interpolation_enabled,
                "targetFps": 60,
                "multi": 2,
                "algorithm": "rife",
                "model": "4.25",
                "onnxModel": "",
                "scale": 1.0,
                "fp16": False,
                "tensorBackend": "pytorch",
                "engine": "cuda",
            },
            "superResolution": {
                "enabled": True,
                "scaleFactor": 4.0,
                "algorithm": "ppmsvsr",
                "onnxModel": "",
                "tensorBackend": "paddle",
                "engine": engine,
                "numFrames": num_frames,
            },
            "preprocess": {"enabled": False, "filters": []},
            "postprocess": {"enabled": False, "filters": []},
        },
        "encode": {
            "codec": "libx264",
            "family": "cpu",
            "container": "mp4",
            "keepAudio": False,
            "rateControl": {"mode": "crf", "value": 28},
            "options": {"preset": "ultrafast"},
        },
        "output": {
            "outputDir": str(output_dir),
            "openOnComplete": False,
            "segmentFrames": segment_frames if segment_frames is not None else num_frames,
        },
    }


def run_process(
    *,
    input_path: Path,
    config: dict[str, Any],
    output_path: Path | None = None,
    output_dir: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    assert (output_path is None) != (output_dir is None), "choose exactly one output target"
    output_args = ["--output", str(output_path)] if output_path is not None else ["--output-dir", str(output_dir)]
    return run_app(
        "process",
        "--input",
        str(input_path),
        *output_args,
        "--config-stdin",
        "--resume-mode",
        "force-fresh",
        stdin_json=config,
        extra_env=extra_env,
    )


def assert_completed_process(
    process: subprocess.CompletedProcess[str],
    *,
    processed_frames: int,
    output_path: Path | None = None,
) -> dict[str, Any]:
    assert process.returncode == 0, f"process failed:\nSTDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}"
    completed = last_json_line(process.stdout)
    assert completed["type"] == "completed"
    assert completed["processedFrames"] == processed_frames
    resolved_output = output_path or Path(completed["outputPath"])
    assert_nonempty_file(resolved_output, "processed output")
    return completed


def probe_output(path: Path) -> dict[str, Any]:
    process = run_app("info", "--input", str(path), timeout=60)
    assert process.returncode == 0, f"info failed:\nSTDOUT:\n{process.stdout}\nSTDERR:\n{process.stderr}"
    return last_json_line(process.stdout)


def assert_nonempty_file(path: Path, label: str) -> None:
    assert path.is_file() and path.stat().st_size > 0, f"{label} is required: {path}"
