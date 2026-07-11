"""Report serialisation helpers for benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_markdown_report(report: dict[str, Any]) -> str:
    workload = report.get("workload", {})
    summary = report.get("summary", {}).get("median", {})
    comparison = report.get("comparison") or {}
    lines = [
        "# VP Workbench Benchmark",
        "",
        f"- Scenario: `{report.get('name', '')}`",
        f"- Workload: {workload.get('width')}x{workload.get('height')} @ {workload.get('fps')}fps, "
        f"{workload.get('frames')} frames, multi={workload.get('multi')}, backend={workload.get('backend')}",
        f"- Median wall time: `{summary.get('wallTimeSeconds', 0)}` seconds",
        f"- Median throughput: `{summary.get('throughputFps', 0)}` fps",
        f"- H2D/D2H counts: `{summary.get('transferCounts', {})}`",
        f"- H2D/D2H seconds: `{summary.get('transferDurationsSeconds', {})}`",
    ]
    if comparison:
        status = "PASS" if comparison.get("passed") else "FAIL"
        lines.extend(["", f"## Baseline Comparison: {status}", ""])
        regressions = comparison.get("regressions") or []
        if regressions:
            lines.append("| Metric | Current | Baseline | Direction |")
            lines.append("|---|---:|---:|---|")
            for item in regressions:
                lines.append(f"| `{item['metric']}` | {item['current']} | {item['baseline']} | {item['direction']} |")
        else:
            lines.append("No regressions exceeded the configured threshold.")
    return "\n".join(lines) + "\n"


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_markdown_report(report), encoding="utf-8")
