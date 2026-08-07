"""Bundled CUDA/TensorRT smoke matrix.

This file intentionally lives outside ``tests/`` so default pytest does not
collect it. Run explicitly on machines with real CUDA/TensorRT runtimes and
bundled model weights.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from tests_full_e2e.helpers import try_last_json_line

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
REPORT_DIR = REPO_ROOT / "test-results"
REPORT_JSON = REPORT_DIR / "inference-matrix.json"
REPORT_MD = REPORT_DIR / "inference-matrix.md"
WORKER_TIMEOUT_SECONDS = int(os.environ.get("VP_INFERENCE_MATRIX_CASE_TIMEOUT", "900"))
RIFE_SMOKE_MODELS = ("4.25",)


WORKER_CODE = r"""
import json
import logging
import os
import time
import traceback
from pathlib import Path

import numpy as np

TEST_SIZE = 128
PADDLEGAN_LINEAR_SCALE = 4


def _quiet_framework_loggers():
    for name in (
        "torch_tensorrt",
        "torch_tensorrt.dynamo",
        "tensorrt",
        "paddle",
        "paddle.tensorrt",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def _torch_memory(torch):
    if not torch.cuda.is_available():
        return {}
    torch.cuda.synchronize()
    return {
        "maxMemoryAllocatedBytes": int(torch.cuda.max_memory_allocated()),
        "maxMemoryReservedBytes": int(torch.cuda.max_memory_reserved()),
    }


def _paddle_memory(paddle):
    sync = getattr(getattr(paddle, "device", None), "synchronize", None)
    if callable(sync):
        sync()
    cuda = getattr(getattr(paddle, "device", None), "cuda", None)
    out = {}
    for public, fn_name in (
        ("maxMemoryAllocatedBytes", "max_memory_allocated"),
        ("maxMemoryReservedBytes", "max_memory_reserved"),
    ):
        fn = getattr(cuda, fn_name, None)
        if callable(fn):
            out[public] = int(fn())
    return out


def _reset_torch_memory(torch):
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def _reset_paddle_memory(paddle):
    cuda = getattr(getattr(paddle, "device", None), "cuda", None)
    for name in ("reset_max_memory_reserved", "reset_max_memory_allocated"):
        fn = getattr(cuda, name, None)
        if callable(fn):
            fn()


def _run_rife_pytorch(case):
    import torch

    from app.algorithms.pytorch.rife.solver import RIFESolver

    _quiet_framework_loggers()
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch CUDA is not available.")
    _reset_torch_memory(torch)
    solver = RIFESolver(
        model_version=case["model"],
        model_dir=case["model_root"],
        device="cuda",
        fp16=False,
        engine=case["engine"],
    )
    img0 = torch.rand((1, 3, TEST_SIZE, TEST_SIZE), device="cuda", dtype=torch.float32)
    img1 = torch.rand((1, 3, TEST_SIZE, TEST_SIZE), device="cuda", dtype=torch.float32)
    started = time.perf_counter()
    output = solver.interpolate(img0, img1)
    torch.cuda.synchronize()
    return {
        "status": "passed",
        "device": str(output.device),
        "dtype": str(output.dtype),
        "outputShape": list(output.shape),
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        **_torch_memory(torch),
    }


def _run_rife_onnx(case):
    from app.algorithms.pytorch.rife.onnx_solver import RIFEONNXSolver

    _quiet_framework_loggers()
    solver = RIFEONNXSolver(
        model_version=case["model"],
        model_dir=case["model_root"],
        engine=case["engine"],
    )
    img0 = np.random.default_rng(0).random((1, 3, TEST_SIZE, TEST_SIZE), dtype=np.float32)
    img1 = np.random.default_rng(1).random((1, 3, TEST_SIZE, TEST_SIZE), dtype=np.float32)
    started = time.perf_counter()
    output = solver.interpolate(img0, img1)
    providers = list(solver._session.get_providers())
    expected = "TensorrtExecutionProvider" if case["engine"] == "tensorrt" else "CUDAExecutionProvider"
    if expected not in providers:
        raise RuntimeError(f"ONNX session did not bind {expected}; providers={providers}")
    return {
        "status": "passed",
        "providers": providers,
        "outputShape": list(output.shape),
        "elapsedSeconds": round(time.perf_counter() - started, 6),
    }


def _run_paddlegan(case):
    import paddle

    from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner

    _quiet_framework_loggers()
    if not paddle.device.is_compiled_with_cuda():
        raise RuntimeError("Paddle CUDA is not available.")
    paddle.set_device("gpu")
    _reset_paddle_memory(paddle)
    frames = [
        np.random.default_rng(seed).integers(0, 256, size=(TEST_SIZE, TEST_SIZE, 3), dtype=np.uint8)
        for seed in range(5)
    ]
    runner = PaddleGanVsrRunner(model_id=case["model"], num_frames=5, engine=case["engine"])
    started = time.perf_counter()
    output = runner.process_frames(frames)
    if len(output) != 5:
        raise RuntimeError(f"Expected 5 output frames, got {len(output)}")
    first_shape = list(output[0].shape)
    expected_shape = [TEST_SIZE * PADDLEGAN_LINEAR_SCALE, TEST_SIZE * PADDLEGAN_LINEAR_SCALE, 3]
    if first_shape != expected_shape:
        raise RuntimeError(f"Expected 4x VSR frame shape {expected_shape}, got {first_shape}")
    return {
        "status": "passed",
        "device": paddle.device.get_device(),
        "outputFrameCount": len(output),
        "outputShape": first_shape,
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        **_paddle_memory(paddle),
    }


def main():
    case = json.loads(os.environ["VP_INFERENCE_MATRIX_CASE"])
    try:
        if case["family"] == "rife-pytorch":
            payload = _run_rife_pytorch(case)
        elif case["family"] == "rife-onnx":
            payload = _run_rife_onnx(case)
        elif case["family"] == "paddlegan":
            payload = _run_paddlegan(case)
        else:
            raise RuntimeError(f"Unknown case family: {case['family']}")
    except Exception as exc:
        payload = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    payload.update({
        "family": case["family"],
        "model": case["model"],
        "engine": case["engine"],
        "tensorBackend": case["tensorBackend"],
    })
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if payload["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
"""


def _matrix_cases() -> list[dict[str, Any]]:
    model_root = str(BACKEND_DIR / "models")
    cases: list[dict[str, Any]] = []
    for model in RIFE_SMOKE_MODELS:
        for engine in ("cuda", "tensorrt"):
            cases.append(
                {
                    "family": "rife-pytorch",
                    "tensorBackend": "pytorch",
                    "engine": engine,
                    "model": model,
                    "model_root": model_root,
                }
            )
            cases.append(
                {
                    "family": "rife-onnx",
                    "tensorBackend": "onnx",
                    "engine": engine,
                    "model": model,
                    "model_root": model_root,
                }
            )
    for model in PADDLEGAN_VSR_SPECS:
        for engine in ("cuda", "tensorrt"):
            cases.append(
                {
                    "family": "paddlegan",
                    "tensorBackend": "paddle",
                    "engine": engine,
                    "model": model,
                    "model_root": model_root,
                }
            )
    return cases


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["VP_DEBUG"] = "false"
    env["VP_INFERENCE_MATRIX_CASE"] = json.dumps(case, ensure_ascii=False)
    env.setdefault("VP_LOG_DIR", str(REPORT_DIR / "logs"))
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
            "family": case["family"],
            "model": case["model"],
            "engine": case["engine"],
            "tensorBackend": case["tensorBackend"],
            "error": f"worker returned {proc.returncode} without JSON payload",
        }
    payload["returnCode"] = proc.returncode
    if proc.stderr:
        payload["stderrTail"] = proc.stderr[-4000:]
    if proc.stdout:
        payload["stdoutTail"] = proc.stdout[-4000:]
    return payload


def _write_reports(results: list[dict[str, Any]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total": len(results),
        "passed": sum(1 for item in results if item.get("status") == "passed"),
        "failed": sum(1 for item in results if item.get("status") != "passed"),
        "results": results,
    }
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Inference Matrix",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        "",
        "| Status | Family | Backend | Engine | Model | Elapsed | Detail |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for item in results:
        detail = item.get("error") or ",".join(str(v) for v in item.get("outputShape", []))
        lines.append(
            "| {status} | {family} | {backend} | {engine} | {model} | {elapsed} | {detail} |".format(
                status=item.get("status"),
                family=item.get("family"),
                backend=item.get("tensorBackend"),
                engine=item.get("engine"),
                model=item.get("model"),
                elapsed=item.get("elapsedSeconds", ""),
                detail=str(detail).replace("|", "\\|")[:200],
            )
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.full_e2e
def test_paddlegan_all_models_and_rife_smoke_cuda_tensorrt_matrix() -> None:
    cases = _matrix_cases()
    results = []
    for index, case in enumerate(cases, start=1):
        result = _run_case(case)
        results.append(result)
        _write_reports(results)
        print(
            "[{index}/{total}] {status} {family} {backend}/{engine} {model}".format(
                index=index,
                total=len(cases),
                status=result.get("status"),
                family=case["family"],
                backend=case["tensorBackend"],
                engine=case["engine"],
                model=case["model"],
            ),
            flush=True,
        )
    failures = [item for item in results if item.get("status") != "passed"]
    assert not failures, (
        f"{len(failures)} inference matrix cases failed. "
        f"See {REPORT_JSON} and {REPORT_MD}. First failure: {failures[0] if failures else None}"
    )
