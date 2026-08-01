"""Compose reviewed boundaries, reachability, and Vulture gates."""

from __future__ import annotations

from .reachability import validate_production_reachability
from .reviewed import (
    _FULL_SCAN_ONLY_REVIEWED_SYMBOLS,
    _PRODUCTION_REVIEWED_SYMBOLS,
    _validate_handler_symbols,
    _validate_reviewed_exclusions,
    _validate_reviewed_symbols,
)
from .vulture_gate import run_vulture_gate


def main() -> int:
    _validate_reviewed_exclusions()
    _validate_reviewed_symbols()
    _validate_handler_symbols()
    validate_production_reachability()
    production = run_vulture_gate(
        ["backend/app", "backend/export_all_rife_onnx.py"],
        _PRODUCTION_REVIEWED_SYMBOLS,
        required_reviewed_symbols=_PRODUCTION_REVIEWED_SYMBOLS,
    )
    if production:
        return production
    return run_vulture_gate(
        ["backend/app", "backend/tests", "backend/tests_full_e2e", "backend/export_all_rife_onnx.py", "scripts"],
        (*_PRODUCTION_REVIEWED_SYMBOLS, *_FULL_SCAN_ONLY_REVIEWED_SYMBOLS),
        required_reviewed_symbols=_FULL_SCAN_ONLY_REVIEWED_SYMBOLS,
    )


__all__ = ["main"]
