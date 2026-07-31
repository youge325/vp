"""Regression coverage for reviewed Python dead-code exclusions."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_python_dead_code import (  # noqa: E402
    _REVIEWED_EXCLUSIONS,
    _find_unreachable_production_modules,
    _rife_module_paths,
    _validate_reviewed_exclusions,
)


def test_python_dead_code_exclusions_are_exact_reviewed_boundaries() -> None:
    static_paths = {
        "backend/app/algorithms/paddle/paddlegan_vsr/vendor/",
        "backend/app/generated/contracts.py",
        "backend/app/generated/protocol_constants.py",
    }
    assert {entry.path for entry in _REVIEWED_EXCLUSIONS} == static_paths | set(_rife_module_paths())
    assert all(entry.reason and entry.evidence_file and entry.evidence_marker for entry in _REVIEWED_EXCLUSIONS)
    _validate_reviewed_exclusions()


def test_python_production_reachability_rejects_a_dead_dependency_cycle(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "__init__.py").write_text("", encoding="utf-8")
    (app_root / "__main__.py").write_text("from app.live import VALUE\n", encoding="utf-8")
    (app_root / "live.py").write_text("from app.shared import VALUE\n", encoding="utf-8")
    (app_root / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (app_root / "dead_a.py").write_text("from app.dead_b import VALUE\n", encoding="utf-8")
    (app_root / "dead_b.py").write_text("from app.dead_a import VALUE\n", encoding="utf-8")

    assert _find_unreachable_production_modules(app_root) == {"app.dead_a", "app.dead_b"}
