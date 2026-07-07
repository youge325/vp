"""Real PP-MSVSR numFrames + VRAM e2e.

This file intentionally lives outside ``tests/`` so default pytest does not
collect it. Run explicitly on machines with Paddle CUDA and real PP-MSVSR
weights installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.utils.model_metrics import get_paddlegan_model_detail

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
PADDLEGAN_WEIGHT = BACKEND_DIR / "models" / "super_resolution" / "paddlegan" / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
WIDTH = 640
HEIGHT = 288
NUM_FRAMES = 5


def _run_python_probe(module_name: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"Required module {module_name!r} is not importable in a subprocess.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _run_paddle_cuda_probe() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import paddle; raise SystemExit(0 if paddle.device.is_compiled_with_cuda() else 1)",
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        "Paddle CUDA support is required for this real VRAM e2e test.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
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
            f"testsrc=duration=0.2:size={WIDTH}x{HEIGHT}:rate=27",
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
    env["VP_LOG_DIR"] = tempfile.mkdtemp(prefix="vp-full-e2e-logs-")
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
            lines.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return lines


def _last_json_line(stdout: str) -> dict[str, Any]:
    lines = _json_lines(stdout)
    if not lines:
        raise AssertionError(f"No JSON lines found in stdout:\n{stdout}")
    return lines[-1]


def _trace_lines(path: Path) -> list[dict[str, Any]]:
    assert path.is_file(), f"PP-MSVSR trace file was not written: {path}"
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            lines.append(json.loads(line))
    assert lines, f"PP-MSVSR trace file was empty: {path}"
    return lines


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
                "engine": "cuda",
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


def _expected_ppmsvsr_vram_bytes() -> float:
    metrics = get_paddlegan_model_detail("ppmsvsr")["metrics"]
    return (
        metrics["runtimeOverheadBytes"]
        + metrics["parameterBytes"]
        + metrics["activationBytesPerMegapixel"] * (WIDTH * HEIGHT / 1_000_000.0) * NUM_FRAMES
    )


@pytest.mark.full_e2e
def test_ppmsvsr_num_frames_reaches_runner_and_reserved_vram_matches_estimate(tmp_path: Path) -> None:
    _run_python_probe("paddle")
    _run_paddle_cuda_probe()
    assert PADDLEGAN_WEIGHT.is_file() and PADDLEGAN_WEIGHT.stat().st_size > 0, (
        f"PaddleGAN PP-MSVSR weight is required for this real e2e test: {PADDLEGAN_WEIGHT}"
    )

    input_path = tmp_path / "ppmsvsr-nf5-input.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "ppmsvsr-nf5-output.mp4"
    trace_path = tmp_path / "paddlegan-trace.jsonl"
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
        extra_env={"VP_PADDLEGAN_VSR_TRACE_PATH": str(trace_path)},
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

    trace = _trace_lines(trace_path)[-1]
    assert trace["modelId"] == "ppmsvsr"
    assert trace["configuredNumFrames"] == NUM_FRAMES
    assert trace["inputFrameCount"] == NUM_FRAMES
    assert [chunk["chunkFrameCount"] for chunk in trace["chunks"]] == [NUM_FRAMES]
    assert trace["chunks"][0]["inputShape"] == [1, NUM_FRAMES, 3, HEIGHT, WIDTH]
    assert trace["chunks"][0]["outputShape"] == [1, NUM_FRAMES, 3, HEIGHT * 4, WIDTH * 4]

    reserved = trace["maxMemoryReservedBytes"]
    allocated = trace["maxMemoryAllocatedBytes"]
    expected = _expected_ppmsvsr_vram_bytes()
    assert reserved > 0
    assert allocated > 0
    assert expected * 0.75 <= reserved <= expected * 1.10
