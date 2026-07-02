"""Real PyTorch RIFE + PaddleGAN VSR CLI e2e.

This file intentionally lives outside ``tests/`` so the default pytest
``testpaths`` does not collect it. Run it explicitly in environments with the
real PyTorch/Paddle runtimes and PaddleGAN weights installed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
PADDLEGAN_WEIGHT = BACKEND_DIR / "models" / "super_resolution" / "paddlegan" / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
TERMINAL_PROGRESS_FPS_RE = re.compile(r"\|\s+\d+\.\d fps\s+\|")


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


def _run_app(*args: str, stdin_json: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["VP_LOG_DIR"] = tempfile.mkdtemp(prefix="vp-full-e2e-logs-")

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
            "testsrc=duration=0.1:size=64x64:rate=30",
            "-frames:v",
            "3",
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


def _json_lines(stdout: str) -> list[dict]:
    lines: list[dict] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            lines.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return lines


def _last_json_line(stdout: str) -> dict:
    lines = _json_lines(stdout)
    if not lines:
        raise AssertionError(f"No JSON lines found in stdout:\n{stdout}")
    return lines[-1]


def _terminal_progress_lines(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if line.startswith("[VP_PROGRESS]")]


def _process_config(output_dir: Path) -> dict:
    return {
        "workflow": {
            "fpsMode": "multi",
            "processOrder": "frame_interpolation_then_super_resolution",
            "interpolation": {
                "enabled": True,
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
                "numFrames": 8,
                "autoDownloadWeights": False,
            },
            "anime": {"enabled": False, "profile": "clean-lines", "denoise": 10, "edgeBoost": 15},
            "preprocess": {"enabled": False, "filters": []},
            "postprocess": {"enabled": False, "filters": []},
        },
        "output": {
            "outputDir": str(output_dir),
            "openOnComplete": False,
            "segmentFrames": 1000,
        },
    }


@pytest.mark.full_e2e
def test_cli_process_runs_real_pytorch_interpolation_then_paddlegan_super_resolution(tmp_path: Path) -> None:
    _run_python_probe("torch")
    _run_python_probe("paddle")
    assert PADDLEGAN_WEIGHT.is_file() and PADDLEGAN_WEIGHT.stat().st_size > 0, (
        f"PaddleGAN PP-MSVSR weight is required for this real e2e test: {PADDLEGAN_WEIGHT}"
    )

    input_path = tmp_path / "pytorch-paddle-input.mp4"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _generate_input_video(input_path)

    proc = _run_app(
        "process",
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
        "--config-stdin",
        "--resume-mode",
        "force-fresh",
        stdin_json=_process_config(output_dir),
    )

    assert proc.returncode == 0, f"process failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    events = _json_lines(proc.stdout)
    progress_stages = {event.get("stage") for event in events if event.get("type") == "progress"}
    assert {"01_frame_interpolation", "02_super_resolution"}.issubset(progress_stages)
    super_resolution_progress = [
        event for event in events if event.get("type") == "progress" and event.get("stage") == "02_super_resolution"
    ]
    assert any(event.get("current") for event in super_resolution_progress), (
        f"No non-zero super-resolution progress event found in stdout:\n{proc.stdout}"
    )
    terminal_progress = _terminal_progress_lines(proc.stderr)
    assert any("[1/2 01_frame_interpolation]" in line for line in terminal_progress), (
        f"No interpolation terminal progress line found in stderr:\n{proc.stderr}"
    )
    assert any("[2/2 02_super_resolution]" in line for line in terminal_progress), (
        f"No super-resolution terminal progress line found in stderr:\n{proc.stderr}"
    )
    assert any("[1/2 01_frame_interpolation]" in line and "100.0%" in line for line in terminal_progress), (
        f"No completed interpolation terminal progress line found in stderr:\n{proc.stderr}"
    )
    assert any("[2/2 02_super_resolution]" in line and "100.0%" in line for line in terminal_progress), (
        f"No completed super-resolution terminal progress line found in stderr:\n{proc.stderr}"
    )
    nonzero_terminal_progress = [line for line in terminal_progress if not re.search(r"\s0/\d+\s", line)]
    assert nonzero_terminal_progress, f"No non-zero terminal progress lines found in stderr:\n{proc.stderr}"
    assert all("--.- fps" not in line for line in nonzero_terminal_progress)
    assert any(TERMINAL_PROGRESS_FPS_RE.search(line) for line in nonzero_terminal_progress)

    completed = events[-1]
    assert completed.get("type") == "completed"
    assert completed.get("processedFrames") == 5
    output_path = Path(completed["outputPath"])
    assert output_path.is_file() and output_path.stat().st_size > 0

    info = _run_app("info", "--input", str(output_path), timeout=60)
    assert info.returncode == 0, f"info failed:\nSTDOUT:\n{info.stdout}\nSTDERR:\n{info.stderr}"
    metadata = _last_json_line(info.stdout)
    assert metadata["width"] == 256
    assert metadata["height"] == 256
    assert metadata["frames"] == 5
