"""``python -m app benchmark`` handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.benchmark.comparison import compare_reports
from app.benchmark.reporting import write_json_report, write_markdown_report
from app.benchmark.runner import BenchmarkOptions, Workload, default_baseline_path, default_work_dir, run_benchmark
from app.benchmark.scenarios import DEFAULT_SCENARIO
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError


def _load_baseline(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProcessError(
            TaskErrorCode.INVALID_CONFIG,
            f"Baseline file does not exist: {path}",
            details={"baselinePath": str(path)},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProcessError(
            TaskErrorCode.INVALID_CONFIG,
            f"Baseline file is not valid JSON: {path}",
            details={"baselinePath": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict) or "summary" not in payload:
        raise ProcessError(
            TaskErrorCode.INVALID_CONFIG,
            f"Baseline file has an unsupported schema: {path}",
            details={"baselinePath": str(path)},
        )
    return payload


def _write_reports(report: dict[str, Any], *, json_path: Path | None, markdown_path: Path | None) -> None:
    if json_path is not None:
        write_json_report(report, json_path)
    if markdown_path is not None:
        write_markdown_report(report, markdown_path)


def _workload_from_args(args: argparse.Namespace) -> Workload:
    return Workload(
        scenario=args.scenario or DEFAULT_SCENARIO,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frames=args.frames,
        multi=args.multi,
        backend=args.backend,
        model=args.model,
    )


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Run benchmark, write reports, and optionally compare/update a baseline."""
    workload = _workload_from_args(args)
    options = BenchmarkOptions(
        workload=workload,
        work_dir=Path(args.work_dir) if args.work_dir else default_work_dir(),
        warmup_runs=args.warmup_runs,
        runs=args.runs,
    )
    report = run_benchmark(options)

    baseline_path = Path(args.baseline) if args.baseline else default_baseline_path()
    json_path = Path(args.report_json) if args.report_json else None
    markdown_path = Path(args.report_markdown) if args.report_markdown else None

    if args.update_baseline:
        write_json_report(report, baseline_path)
        comparison = {
            "baselineName": report.get("name"),
            "threshold": args.threshold,
            "passed": True,
            "regressions": [],
            "updatedBaseline": str(baseline_path),
        }
    else:
        try:
            baseline = _load_baseline(baseline_path)
        except BaseException:
            _write_reports(report, json_path=json_path, markdown_path=markdown_path)
            raise
        comparison = compare_reports(current=report, baseline=baseline, threshold=args.threshold)

    report["comparison"] = comparison
    _write_reports(report, json_path=json_path, markdown_path=markdown_path)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not comparison["passed"]:
        raise ProcessError(
            TaskErrorCode.PROCESS_FAILED,
            "Benchmark regression detected.",
            details={"comparison": comparison, "baselinePath": str(baseline_path)},
        )
