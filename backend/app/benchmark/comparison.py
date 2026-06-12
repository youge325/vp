"""Baseline comparison helpers for benchmark reports."""

from __future__ import annotations

from typing import Any


def _get_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Benchmark report is missing required metric: {path}")
        current = current[part]
    return current


def _regression(metric: str, current: float, baseline: float, threshold: float, direction: str) -> dict[str, Any]:
    if baseline == 0:
        delta_ratio = 0.0 if current == 0 else float("inf")
    else:
        delta_ratio = (current - baseline) / baseline
    return {
        "metric": metric,
        "current": current,
        "baseline": baseline,
        "threshold": threshold,
        "direction": direction,
        "deltaRatio": round(delta_ratio, 6) if delta_ratio != float("inf") else delta_ratio,
    }


def _compare_lower_is_worse(
    *,
    metric: str,
    current: dict[str, Any],
    baseline: dict[str, Any],
    threshold: float,
    regressions: list[dict[str, Any]],
) -> None:
    current_value = float(_get_path(current, metric))
    baseline_value = float(_get_path(baseline, metric))
    if current_value < baseline_value * (1.0 - threshold):
        regressions.append(_regression(metric, current_value, baseline_value, threshold, "lower_is_worse"))


def _compare_higher_is_worse(
    *,
    metric: str,
    current: dict[str, Any],
    baseline: dict[str, Any],
    threshold: float,
    regressions: list[dict[str, Any]],
) -> None:
    current_value = float(_get_path(current, metric))
    baseline_value = float(_get_path(baseline, metric))
    if current_value > baseline_value * (1.0 + threshold):
        regressions.append(_regression(metric, current_value, baseline_value, threshold, "higher_is_worse"))


def _compare_transfer_count(
    *,
    metric: str,
    current: dict[str, Any],
    baseline: dict[str, Any],
    regressions: list[dict[str, Any]],
) -> None:
    current_value = int(_get_path(current, metric))
    baseline_value = int(_get_path(baseline, metric))
    if current_value > baseline_value:
        regressions.append(
            {
                "metric": metric,
                "current": current_value,
                "baseline": baseline_value,
                "threshold": 0.0,
                "direction": "strict_upper_bound",
                "deltaRatio": round((current_value - baseline_value) / max(baseline_value, 1), 6),
            }
        )


def _nested_metric_paths(report: dict[str, Any], parent: str) -> list[str]:
    value = _get_path(report, parent)
    if not isinstance(value, dict):
        raise ValueError(f"Benchmark report metric group must be an object: {parent}")
    return [f"{parent}.{key}" for key in sorted(value)]


def compare_reports(*, current: dict[str, Any], baseline: dict[str, Any], threshold: float) -> dict[str, Any]:
    """Compare a benchmark report to a baseline report.

    Throughput metrics regress when they drop below baseline by more than
    ``threshold``. Duration metrics regress when they rise above baseline by
    more than ``threshold``. Transfer counts are strict upper bounds because
    extra host/device crossings are usually structural regressions.
    """
    regressions: list[dict[str, Any]] = []

    _compare_lower_is_worse(
        metric="summary.median.throughputFps",
        current=current,
        baseline=baseline,
        threshold=threshold,
        regressions=regressions,
    )

    for metric in [
        "summary.median.wallTimeSeconds",
        "summary.median.completedTimeSeconds",
        *_nested_metric_paths(current, "summary.median.stageDurationsSeconds"),
        *_nested_metric_paths(current, "summary.median.transferDurationsSeconds"),
    ]:
        _compare_higher_is_worse(
            metric=metric,
            current=current,
            baseline=baseline,
            threshold=threshold,
            regressions=regressions,
        )

    for metric in _nested_metric_paths(current, "summary.median.transferCounts"):
        _compare_transfer_count(metric=metric, current=current, baseline=baseline, regressions=regressions)

    return {
        "baselineName": baseline.get("name") or baseline.get("scenario"),
        "threshold": threshold,
        "passed": not regressions,
        "regressions": regressions,
    }
