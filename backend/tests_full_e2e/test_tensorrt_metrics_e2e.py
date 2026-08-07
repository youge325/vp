"""TensorRT metric calibration E2E checks.

Run explicitly on machines with Paddle CUDA/TensorRT and bundled VSR weights:

    python -m pytest tests_full_e2e/test_tensorrt_metrics_e2e.py -q -m full_e2e --tb=short
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.catalog.model_metrics import MODEL_METRIC_SPECS_BY_ALGORITHM
from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from tests_full_e2e.helpers import try_last_json_line

BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKER_TIMEOUT_SECONDS = int(os.environ.get("VP_TENSORRT_METRICS_CASE_TIMEOUT", "900"))

WORKER_CODE = r"""
import json
import os
import time
import traceback

import numpy as np

case = json.loads(os.environ["VP_TENSORRT_METRICS_CASE"])
try:
    import paddle

    from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner

    def reset_memory():
        cuda = getattr(getattr(paddle, "device", None), "cuda", None)
        for name in ("reset_max_memory_reserved", "reset_max_memory_allocated"):
            fn = getattr(cuda, name, None)
            if callable(fn):
                fn()

    def memory():
        sync = getattr(getattr(paddle, "device", None), "synchronize", None)
        if callable(sync):
            sync()
        cuda = getattr(getattr(paddle, "device", None), "cuda", None)
        result = {}
        for public, fn_name in (
            ("maxMemoryAllocatedBytes", "max_memory_allocated"),
            ("maxMemoryReservedBytes", "max_memory_reserved"),
        ):
            fn = getattr(cuda, fn_name, None)
            if callable(fn):
                result[public] = int(fn())
        return result

    if not paddle.device.is_compiled_with_cuda():
        raise RuntimeError("Paddle CUDA is not available.")
    paddle.set_device("gpu")
    reset_memory()
    height = int(case["height"])
    width = int(case["width"])
    num_frames = int(case["numFrames"])
    frames = [
        np.random.default_rng(seed).integers(0, 256, size=(height, width, 3), dtype=np.uint8)
        for seed in range(num_frames)
    ]
    runner = PaddleGanVsrRunner(model_id=case["model"], num_frames=num_frames, engine="tensorrt")
    started = time.perf_counter()
    output = runner.process_frames(frames)
    payload = {
        "status": "passed",
        "model": case["model"],
        "width": width,
        "height": height,
        "numFrames": num_frames,
        "outputFrameCount": len(output),
        "outputShape": list(output[0].shape) if output else None,
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        **memory(),
    }
except Exception as exc:
    payload = {
        "status": "failed",
        "model": case.get("model"),
        "width": case.get("width"),
        "height": case.get("height"),
        "error": f"{type(exc).__name__}: {exc}",
        "traceback": traceback.format_exc(),
    }
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if payload["status"] == "passed" else 1)
"""


def _run_case(case: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["VP_DEBUG"] = "false"
    env["VP_TENSORRT_METRICS_CASE"] = json.dumps(case, ensure_ascii=False)
    env["VP_LOG_DIR"] = str(tmp_path / "logs")
    env["VP_PADDLEGAN_TRT_CACHE_DIR"] = str(tmp_path / "trt-cache")
    proc = subprocess.run(
        [sys.executable, "-c", WORKER_CODE],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=WORKER_TIMEOUT_SECONDS,
        check=False,
    )
    payload = try_last_json_line(proc.stdout)
    if payload is None:
        payload = {
            "status": "failed",
            "model": case["model"],
            "error": f"worker returned {proc.returncode} without JSON payload",
        }
    payload["returnCode"] = proc.returncode
    if proc.stdout:
        payload["stdoutTail"] = proc.stdout[-3000:]
    if proc.stderr:
        payload["stderrTail"] = proc.stderr[-3000:]
    return payload


def _expected_vram_bytes(model_id: str, *, width: int, height: int, num_frames: int) -> float:
    metrics = MODEL_METRIC_SPECS_BY_ALGORITHM[model_id][0]
    tensorrt = dict(metrics.engine_metrics)["tensorrt"]
    frame_count = tensorrt.runtime_frame_count or num_frames
    megapixels = (width * height) / 1_000_000
    return (
        (tensorrt.runtime_overhead_bytes or 0)
        + (metrics.parameter_bytes or 0)
        + (tensorrt.activation_bytes_per_megapixel or 0) * megapixels * frame_count
    )


@pytest.mark.full_e2e
def test_paddlegan_tensorrt_metrics_match_ppmsvsr_reserved_peak(tmp_path: Path) -> None:
    case = {"model": "ppmsvsr", "width": 640, "height": 288, "numFrames": 5}

    result = _run_case(case, tmp_path)

    assert result["status"] == "passed", result
    assert result["outputShape"] == [1152, 2560, 3]
    assert result["outputFrameCount"] == 5
    reserved = result["maxMemoryReservedBytes"]
    expected = _expected_vram_bytes("ppmsvsr", width=640, height=288, num_frames=5)
    assert expected * 0.75 <= reserved <= expected * 1.10


@pytest.mark.full_e2e
def test_all_paddlegan_tensorrt_models_run_in_independent_processes(tmp_path: Path) -> None:
    results = []
    for model_id in PADDLEGAN_VSR_SPECS:
        result = _run_case(
            {"model": model_id, "width": 128, "height": 128, "numFrames": 5},
            tmp_path / model_id,
        )
        results.append(result)
        assert result["status"] == "passed", result
        assert result["outputShape"] == [512, 512, 3]
        assert result["outputFrameCount"] == 5
        assert result["maxMemoryReservedBytes"] > 0

    assert {result["model"] for result in results} == set(PADDLEGAN_VSR_SPECS)
