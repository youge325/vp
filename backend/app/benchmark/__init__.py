"""Benchmark regression support for VP Workbench."""

from __future__ import annotations

from app.benchmark.comparison import compare_reports
from app.benchmark.runner import BenchmarkOptions, Workload, run_benchmark

__all__ = ["BenchmarkOptions", "Workload", "compare_reports", "run_benchmark"]
