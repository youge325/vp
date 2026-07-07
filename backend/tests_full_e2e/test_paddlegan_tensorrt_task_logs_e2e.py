"""Real PaddleGAN TensorRT task-log e2e.

Run explicitly on machines with Paddle CUDA, Paddle Inference TensorRT, ffmpeg,
and PP-MSVSR weights installed:

    python -m pytest tests_full_e2e/test_paddlegan_tensorrt_task_logs_e2e.py -q -m full_e2e --tb=short
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
WEIGHT_ROOT = BACKEND_DIR / "models" / "super_resolution" / "paddlegan"
PPMSVSR_WEIGHT = WEIGHT_ROOT / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
PPMSVSR_AUX_WEIGHT = WEIGHT_ROOT / "_auxiliary" / "modified_spynet_tiny.pdparams"
WIDTH = 128
HEIGHT = 128
NUM_FRAMES = 5


def _run_python_probe(code: str, *, timeout: int = 60) -> None:
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


def _generate_input_video(path: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration=0.2:size={WIDTH}x{HEIGHT}:rate=25",
            "-frames:v",
            str(NUM_FRAMES),
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(path),
            "-y",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"Failed to generate e2e input video:\n{result.stderr}"
    assert path.is_file() and path.stat().st_size > 0


def _run_app(
    *args: str,
    stdin_json: dict[str, Any] | None = None,
    extra_env: dict[str, str] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["VP_LOG_DIR"] = tempfile.mkdtemp(prefix="vp-trt-log-e2e-logs-")
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


def _json_lines(stdout: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            lines.append(payload)
    return lines


def _last_json_line(stdout: str) -> dict[str, Any]:
    lines = _json_lines(stdout)
    assert lines, f"No JSON lines found in stdout:\n{stdout}"
    return lines[-1]


def _process_config(output_dir: Path) -> dict[str, Any]:
    return {
        "decode": {"mode": "software", "hwaccel": "", "decoder": "software", "options": {}},
        "workflow": {
            "fpsMode": "multi",
            "processOrder": "super_resolution_then_interpolation",
            "interpolation": {
                "enabled": False,
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
                "engine": "tensorrt",
                "numFrames": NUM_FRAMES,
                "autoDownloadWeights": False,
            },
            "anime": {"enabled": False, "profile": "clean-lines", "denoise": 10, "edgeBoost": 15},
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
            "segmentFrames": NUM_FRAMES,
        },
    }


@pytest.mark.full_e2e
def test_paddlegan_tensorrt_engine_logs_reach_parent_process_stderr(tmp_path: Path) -> None:
    _run_python_probe("import paddle; raise SystemExit(0 if paddle.device.is_compiled_with_cuda() else 1)")
    assert PPMSVSR_WEIGHT.is_file() and PPMSVSR_WEIGHT.stat().st_size > 0, (
        f"PP-MSVSR weight is required for this real e2e test: {PPMSVSR_WEIGHT}"
    )
    assert PPMSVSR_AUX_WEIGHT.is_file() and PPMSVSR_AUX_WEIGHT.stat().st_size > 0, (
        f"PP-MSVSR auxiliary weight is required for this real e2e test: {PPMSVSR_AUX_WEIGHT}"
    )

    input_path = tmp_path / "ppmsvsr-trt-input.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "ppmsvsr-trt-output.mp4"
    trt_cache_dir = tmp_path / "paddlegan-trt-cache"
    _generate_input_video(input_path)

    proc = _run_app(
        "process",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--config-stdin",
        "--resume-mode",
        "force-fresh",
        stdin_json=_process_config(output_dir),
        extra_env={"VP_PADDLEGAN_TRT_CACHE_DIR": str(trt_cache_dir)},
        timeout=900,
    )

    assert proc.returncode == 0, f"process failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    completed = _last_json_line(proc.stdout)
    assert completed["type"] == "completed"
    assert completed["processedFrames"] == NUM_FRAMES
    assert output_path.is_file() and output_path.stat().st_size > 0

    info = _run_app("info", "--input", str(output_path), timeout=60)
    assert info.returncode == 0, f"info failed:\nSTDOUT:\n{info.stdout}\nSTDERR:\n{info.stderr}"
    metadata = _last_json_line(info.stdout)
    assert metadata["width"] == WIDTH * 4
    assert metadata["height"] == HEIGHT * 4
    assert metadata["frames"] == NUM_FRAMES

    assert "[VP_TRT]" in proc.stderr
    assert re.search(
        r"\d\d:\d\d:\d\d \[INFO\] app\.algorithms\.paddle\.paddlegan_vsr\.runner: "
        r"\[VP_TRT\] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x128x128",
        proc.stderr,
    ) or re.search(
        r"\d\d:\d\d:\d\d \[INFO\] app\.algorithms\.paddle\.paddlegan_vsr\.runner: "
        r"\[VP_TRT\] TensorRT LOAD static_model=",
        proc.stderr,
    )
    assert "[VP_TRT] TensorRT CACHE dir=" in proc.stderr
    assert "[VP_TRT] TensorRT READY outputs=" in proc.stderr
