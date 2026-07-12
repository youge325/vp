"""Tests for the benchmark regression CLI support."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from app.cli.parser import build_parser


def _report(
    *,
    throughput: float,
    wall: float,
    completed: float,
    h2d_count: int = 96,
    d2h_count: int = 95,
    h2d_seconds: float = 1.0,
    d2h_seconds: float = 1.0,
) -> dict:
    return {
        "summary": {
            "median": {
                "throughputFps": throughput,
                "wallTimeSeconds": wall,
                "completedTimeSeconds": completed,
                "stageDurationsSeconds": {
                    "decode": 2.0,
                    "interpolate": 4.0,
                },
                "transferCounts": {
                    "h2d": h2d_count,
                    "d2h": d2h_count,
                },
                "transferDurationsSeconds": {
                    "h2d": h2d_seconds,
                    "d2h": d2h_seconds,
                },
            }
        }
    }


def test_compare_reports_fails_on_throughput_duration_and_transfer_regressions() -> None:
    from app.benchmark.comparison import compare_reports

    baseline = _report(throughput=100.0, wall=10.0, completed=9.0)
    current = _report(
        throughput=80.0,
        wall=12.0,
        completed=11.0,
        h2d_count=97,
        h2d_seconds=1.2,
    )

    comparison = compare_reports(current=current, baseline=baseline, threshold=0.15)

    assert comparison["passed"] is False
    metrics = {item["metric"] for item in comparison["regressions"]}
    assert "summary.median.throughputFps" in metrics
    assert "summary.median.wallTimeSeconds" in metrics
    assert "summary.median.completedTimeSeconds" in metrics
    assert "summary.median.transferCounts.h2d" in metrics
    assert "summary.median.transferDurationsSeconds.h2d" in metrics
    directions = {item["metric"]: item["direction"] for item in comparison["regressions"]}
    assert directions["summary.median.throughputFps"] == "lower_is_worse"
    assert directions["summary.median.wallTimeSeconds"] == "higher_is_worse"


def test_compare_reports_passes_when_current_is_within_threshold() -> None:
    from app.benchmark.comparison import compare_reports

    baseline = _report(throughput=100.0, wall=10.0, completed=9.0)
    current = _report(throughput=90.0, wall=11.0, completed=10.0)

    comparison = compare_reports(current=current, baseline=baseline, threshold=0.15)

    assert comparison["passed"] is True
    assert comparison["regressions"] == []


def test_parse_process_stdout_uses_last_progress_metrics_and_completed_payload() -> None:
    from app.benchmark.runner import _parse_process_stdout

    stdout = "\n".join(
        [
            json.dumps({"type": "progress", "metrics": {"processedFrames": 10}}),
            json.dumps(
                {
                    "type": "progress",
                    "metrics": {
                        "processedFrames": 191,
                        "measuredFps": 12.5,
                        "transferCounts": {"h2d": 96, "d2h": 95},
                    },
                }
            ),
            json.dumps(
                {
                    "type": "completed",
                    "outputPath": "/tmp/out.mp4",
                    "processedFrames": 191,
                    "timeSeconds": 15.25,
                }
            ),
        ]
    )

    result = _parse_process_stdout(stdout)

    assert result["processedFrames"] == 191
    assert result["completedTimeSeconds"] == 15.25
    assert result["metrics"]["processedFrames"] == 191
    assert result["metrics"]["transferCounts"] == {"h2d": 96, "d2h": 95}


def test_build_report_keeps_warmups_out_of_median_summary() -> None:
    from app.benchmark.runner import Workload, _BenchmarkRun, _build_report

    workload = Workload()
    warmup = _BenchmarkRun(
        name="warmup-1",
        warmup=True,
        wall_time_seconds=100.0,
        completed_time_seconds=100.0,
        processed_frames=191,
        metrics={"transferCounts": {"h2d": 96, "d2h": 95}, "transferDurationsSeconds": {"h2d": 10.0, "d2h": 10.0}},
    )
    measured = [
        _BenchmarkRun(
            name=f"run-{index}",
            warmup=False,
            wall_time_seconds=float(value),
            completed_time_seconds=float(value - 1),
            processed_frames=191,
            metrics={
                "stageDurationsSeconds": {"decode": float(index), "interpolate": float(index + 1)},
                "transferCounts": {"h2d": 96, "d2h": 95},
                "transferDurationsSeconds": {"h2d": float(index), "d2h": float(index + 1)},
            },
        )
        for index, value in enumerate([12, 10, 11], start=1)
    ]

    report = _build_report(workload=workload, runs=[warmup, *measured])

    assert len(report["warmupRuns"]) == 1
    assert len(report["runs"]) == 3
    assert report["summary"]["median"]["wallTimeSeconds"] == 11.0
    assert report["summary"]["median"]["completedTimeSeconds"] == 10.0
    assert report["summary"]["median"]["throughputFps"] == pytest.approx(191 / 11)


def test_benchmark_parser_defaults_to_interpolation_cpu_transfer_scenario() -> None:
    parser = build_parser()

    args = parser.parse_args(["benchmark"])

    assert args.func.__name__ == "cmd_benchmark"
    assert args.scenario == "interpolation-e2e-cpu-transfer"
    assert args.threshold == 0.15
    assert args.warmup_runs == 1
    assert args.runs == 3


def test_cmd_benchmark_writes_reports_and_fails_on_missing_baseline(tmp_path: Path, monkeypatch) -> None:
    from app.cli.commands import benchmark as benchmark_command
    from app.errors import ProcessError, TaskErrorCode

    monkeypatch.setattr(
        benchmark_command,
        "run_benchmark",
        lambda _options: _report(throughput=1.0, wall=1.0, completed=1.0),
    )

    args = argparse.Namespace(
        scenario="interpolation-e2e-cpu-transfer",
        baseline=str(tmp_path / "missing.json"),
        threshold=0.15,
        report_json=str(tmp_path / "report.json"),
        report_markdown=str(tmp_path / "report.md"),
        work_dir=str(tmp_path / "work"),
        update_baseline=False,
        warmup_runs=0,
        runs=1,
        width=640,
        height=360,
        fps=24,
        frames=96,
        multi=2,
        backend="pytorch",
        model="4.25",
    )

    with pytest.raises(ProcessError) as exc_info:
        benchmark_command.cmd_benchmark(args)

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "Baseline file does not exist" in exc_info.value.message
    assert (tmp_path / "report.json").is_file()
    assert (tmp_path / "report.md").is_file()
