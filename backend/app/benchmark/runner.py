"""Benchmark runner for the real VP Workbench process pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

from app.config import settings
from app.errors import ProcessError, TaskErrorCode
from app.generated.application_defaults import DEFAULT_RIFE_MODEL_VERSION, DEFAULT_RIFE_MULTI
from app.benchmark.scenarios import DEFAULT_SCENARIO
from app.planning.stage_projection import StageProjection


@dataclass(frozen=True, slots=True)
class Workload:
    """Synthetic interpolation workload used by CI benchmark runs."""

    scenario: str = DEFAULT_SCENARIO
    width: int = 640
    height: int = 360
    fps: int = 24
    frames: int = 96
    multi: int = DEFAULT_RIFE_MULTI
    backend: str = "pytorch"
    model: str = DEFAULT_RIFE_MODEL_VERSION

    @property
    def expected_processed_frames(self) -> int:
        return StageProjection.interpolation_output_frame_count(self.frames, self.multi)


@dataclass(frozen=True, slots=True)
class BenchmarkOptions:
    """Runtime options for ``run_benchmark``."""

    workload: Workload
    work_dir: Path
    warmup_runs: int = 1
    runs: int = 3


@dataclass(frozen=True, slots=True)
class _BenchmarkRun:
    """One warmup or measured process invocation."""

    name: str
    warmup: bool
    wall_time_seconds: float
    completed_time_seconds: float
    processed_frames: int
    metrics: dict[str, Any]

    def to_report(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "wallTimeSeconds": round(self.wall_time_seconds, 3),
            "completedTimeSeconds": round(self.completed_time_seconds, 3),
            "processedFrames": self.processed_frames,
            "metrics": self.metrics,
        }


def _parse_process_stdout(stdout: str) -> dict[str, Any]:
    """Extract the last progress metrics and completed payload from process stdout."""
    last_metrics: dict[str, Any] = {}
    completed: dict[str, Any] | None = None
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "progress":
            metrics = payload.get("metrics")
            if isinstance(metrics, dict):
                last_metrics = metrics
        elif payload.get("type") == "completed":
            completed = payload

    if completed is None:
        raise ValueError("Process stdout did not contain a completed event.")

    return {
        "outputPath": completed.get("outputPath"),
        "processedFrames": int(completed.get("processedFrames") or 0),
        "completedTimeSeconds": float(completed.get("timeSeconds") or 0.0),
        "metrics": last_metrics,
    }


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def _median_map(runs: list[_BenchmarkRun], metrics_key: str) -> dict[str, float]:
    keys: set[str] = set()
    for run in runs:
        group = run.metrics.get(metrics_key)
        if isinstance(group, dict):
            keys.update(str(key) for key in group)
    result: dict[str, float] = {}
    for key in sorted(keys):
        values = [
            float(run.metrics.get(metrics_key, {}).get(key, 0.0))
            for run in runs
            if isinstance(run.metrics.get(metrics_key), dict)
        ]
        result[key] = round(_median(values), 6)
    return result


def _build_report(*, workload: Workload, runs: list[_BenchmarkRun]) -> dict[str, Any]:
    """Build a JSON-serialisable benchmark report.

    Warmups are reported separately and intentionally excluded from median
    summary calculations.
    """
    measured_runs = [run for run in runs if not run.warmup]
    if not measured_runs:
        raise ValueError("At least one measured benchmark run is required.")

    wall_median = _median([run.wall_time_seconds for run in measured_runs])
    completed_median = _median([run.completed_time_seconds for run in measured_runs])
    processed_median = _median([float(run.processed_frames) for run in measured_runs])
    throughput = processed_median / wall_median if wall_median > 0 else 0.0

    return {
        "schemaVersion": 1,
        "name": workload.scenario,
        "workload": asdict(workload),
        "warmupRuns": [run.to_report() for run in runs if run.warmup],
        "runs": [run.to_report() for run in measured_runs],
        "summary": {
            "median": {
                "wallTimeSeconds": round(wall_median, 3),
                "completedTimeSeconds": round(completed_median, 3),
                "processedFrames": int(processed_median),
                "throughputFps": round(throughput, 6),
                "stageDurationsSeconds": _median_map(measured_runs, "stageDurationsSeconds"),
                "transferCounts": {
                    key: int(value) for key, value in _median_map(measured_runs, "transferCounts").items()
                },
                "transferDurationsSeconds": _median_map(measured_runs, "transferDurationsSeconds"),
            }
        },
    }


def _run_checked(
    command: list[str], *, cwd: Path | None = None, timeout: int = 900
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise ProcessError(
            TaskErrorCode.PROCESS_FAILED,
            f"Benchmark command failed: {' '.join(command[:3])}",
            details={
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
    return completed


def _generate_synthetic_input(workload: Workload, input_path: Path) -> None:
    """Generate a deterministic synthetic input video with FFmpeg testsrc2."""
    input_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        settings.FFMPEG_PATH,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={workload.width}x{workload.height}:rate={workload.fps}",
        "-frames:v",
        str(workload.frames),
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        str(input_path),
    ]
    _run_checked(command, timeout=120)


def _process_command(workload: Workload, input_path: Path, output_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "app",
        "process",
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
        "--algorithm",
        "frame_interpolation",
        "--backend",
        workload.backend,
        "--multi",
        str(workload.multi),
        "--model",
        workload.model,
        "--fps-mode",
        "multi",
        "--codec",
        "libx264",
        "--preset",
        "ultrafast",
        "--resume-mode",
        "force-fresh",
    ]


def _run_process_once(
    workload: Workload, *, input_path: Path, output_dir: Path, name: str, warmup: bool
) -> _BenchmarkRun:
    """Run one real ``python -m app process`` invocation and parse its metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    command = _process_command(workload, input_path, output_dir)
    started_at = time.perf_counter()
    completed = _run_checked(command, cwd=settings.backend_root, timeout=1800)
    wall_time_seconds = time.perf_counter() - started_at
    parsed = _parse_process_stdout(completed.stdout)
    processed_frames = int(parsed["processedFrames"])
    if processed_frames != workload.expected_processed_frames:
        raise ProcessError(
            TaskErrorCode.PROCESS_FAILED,
            (
                "Benchmark processed frame count mismatch: "
                f"expected {workload.expected_processed_frames}, got {processed_frames}."
            ),
            details={
                "expectedProcessedFrames": workload.expected_processed_frames,
                "processedFrames": processed_frames,
                "stdout": completed.stdout[-4000:],
            },
        )

    return _BenchmarkRun(
        name=name,
        warmup=warmup,
        wall_time_seconds=wall_time_seconds,
        completed_time_seconds=float(parsed["completedTimeSeconds"]),
        processed_frames=processed_frames,
        metrics=dict(parsed["metrics"]),
    )


def run_benchmark(
    options: BenchmarkOptions,
) -> dict[str, Any]:
    """Run warmup and measured benchmark iterations and return a report."""
    options.work_dir.mkdir(parents=True, exist_ok=True)
    input_path = options.work_dir / "input" / f"{options.workload.scenario}.mp4"
    _generate_synthetic_input(options.workload, input_path)

    all_runs: list[_BenchmarkRun] = []
    for index in range(options.warmup_runs):
        all_runs.append(
            _run_process_once(
                options.workload,
                input_path=input_path,
                output_dir=options.work_dir / f"warmup-{index + 1}",
                name=f"warmup-{index + 1}",
                warmup=True,
            )
        )
    for index in range(options.runs):
        all_runs.append(
            _run_process_once(
                options.workload,
                input_path=input_path,
                output_dir=options.work_dir / f"run-{index + 1}",
                name=f"run-{index + 1}",
                warmup=False,
            )
        )
    return _build_report(workload=options.workload, runs=all_runs)


def default_baseline_path() -> Path:
    return settings.backend_root / "benchmarks" / "baselines" / "linux-arc-pytorch.json"


def default_work_dir() -> Path:
    return settings.backend_root / ".benchmark-work"
