"""Regression coverage for reviewed Python dead-code exclusions."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_python_dead_code import (  # noqa: E402
    _FULL_SCAN_ONLY_REVIEWED_SYMBOLS,
    _PRODUCTION_REVIEWED_SYMBOLS,
    _REVIEWED_EXCLUSIONS,
    ReviewedSymbol,
    _find_unreachable_production_modules,
    _finding_key,
    _protected_module_names,
    _rife_module_paths,
    _scan_unused_code,
    _unreviewed_findings,
    _validate_handler_symbols,
    _validate_reviewed_exclusions,
    _validate_reviewed_symbols,
)


def test_python_dead_code_exclusions_are_exact_reviewed_boundaries() -> None:
    static_paths = {
        "backend/app/algorithms/paddle/paddlegan_vsr/vendor/",
        "backend/app/generated/contracts.py",
        "backend/app/generated/protocol_constants.py",
        "backend/app/generated/stage_worker_contracts.py",
    }
    assert {entry.path for entry in _REVIEWED_EXCLUSIONS} == static_paths | set(_rife_module_paths())
    assert all(entry.reason and entry.evidence_file and entry.evidence_marker for entry in _REVIEWED_EXCLUSIONS)
    _validate_reviewed_exclusions()


def test_reviewed_symbol_cannot_keep_same_named_symbol_in_another_path_alive(tmp_path: Path) -> None:
    reviewed_path = tmp_path / "reviewed.py"
    reviewed_path.write_text("def dynamic_callback():\n    return None\n", encoding="utf-8")
    unreviewed_path = tmp_path / "unreviewed.py"
    unreviewed_path.write_text("def dynamic_callback():\n    return None\n", encoding="utf-8")
    reviewed = ReviewedSymbol(
        path="reviewed.py",
        symbol="dynamic_callback",
        reason="Synthetic dynamic callback boundary.",
        evidence_file="reviewed.py",
        evidence_marker="dynamic_callback",
    )

    findings = _scan_unused_code(
        [reviewed_path, unreviewed_path],
        root=tmp_path,
        exclusions=(),
    )
    unreviewed = _unreviewed_findings(findings, (reviewed,), root=tmp_path)

    assert {_finding_key(item, root=tmp_path) for item in unreviewed} == {("unreviewed.py", "dynamic_callback")}


def test_vulture_gate_does_not_load_global_library_whitelists(tmp_path: Path) -> None:
    source = tmp_path / "production.py"
    source.write_text("import threading\ndef run():\n    return None\n", encoding="utf-8")

    findings = _scan_unused_code([source], root=tmp_path, exclusions=())

    assert ("production.py", "run") in {_finding_key(item, root=tmp_path) for item in findings}


def test_dead_code_hook_triggers_for_gate_and_python_sources() -> None:
    config = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    hook = re.search(
        r"- id: check-python-dead-code.*?files: '([^']+)'",
        config,
        flags=re.DOTALL,
    )
    assert hook is not None
    pattern = re.compile(hook.group(1))

    assert pattern.fullmatch("scripts/check_python_dead_code.py")
    assert pattern.fullmatch("backend/app/config.py")
    assert pattern.fullmatch("backend/tests/test_dead_code_gate.py")


def test_ruff_ignores_are_existing_precise_boundaries() -> None:
    config = tomllib.loads((REPO_ROOT / "ruff.toml").read_text(encoding="utf-8"))
    per_file_ignores = config["lint"]["per-file-ignores"]

    assert "backend/tests/**" not in per_file_ignores
    assert all("*" not in path for path in per_file_ignores if not path.endswith("/vendor/**"))
    for path in per_file_ignores:
        if path.endswith("/vendor/**"):
            assert (REPO_ROOT / path.removesuffix("/**")).is_dir()
        else:
            assert (REPO_ROOT / path).is_file()
    assert all("F401" not in rules for rules in per_file_ignores.values())


def test_stage_worker_generated_exclusion_is_not_a_reachability_root() -> None:
    app_root = REPO_ROOT / "backend/app"
    protected = _protected_module_names(app_root)

    assert "app.generated.stage_worker_contracts" not in protected
    unreachable = _find_unreachable_production_modules(
        app_root,
        entry_files=(REPO_ROOT / "backend/export_all_rife_onnx.py",),
        protected_modules=protected,
    )
    assert "app.generated.stage_worker_contracts" not in unreachable


def test_vulture_cli_handler_evidence_exactly_matches_lazy_registry(tmp_path: Path) -> None:
    handler_path = tmp_path / "main.py"
    handler_path.write_text(
        "_HANDLERS = {'run': ('app.commands.run', 'cmd_run')}\n",
        encoding="utf-8",
    )
    reviewed = (
        ReviewedSymbol(
            path="app/commands/run.py",
            symbol="cmd_run",
            reason="Synthetic lazy handler.",
            evidence_file="main.py",
            evidence_marker="cmd_run",
        ),
    )
    _validate_handler_symbols(handler_path, reviewed)

    stale = (
        *reviewed,
        ReviewedSymbol(
            path="app/commands/stale.py",
            symbol="cmd_stale",
            reason="Synthetic stale handler.",
            evidence_file="main.py",
            evidence_marker="cmd_stale",
        ),
    )
    with pytest.raises(RuntimeError, match="app\\.commands\\.stale.*cmd_stale"):
        _validate_handler_symbols(handler_path, stale)


def test_reviewed_vulture_symbols_are_exact_documented_boundaries() -> None:
    entries = (*_PRODUCTION_REVIEWED_SYMBOLS, *_FULL_SCAN_ONLY_REVIEWED_SYMBOLS)
    keys = {(entry.path, entry.symbol) for entry in entries}

    assert len(keys) == len(entries)
    assert all(entry.reason and entry.evidence_file and entry.evidence_marker for entry in entries)
    _validate_reviewed_symbols()


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


def test_python_production_reachability_follows_lazy_command_registry(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    (app_root / "cli/commands").mkdir(parents=True)
    (app_root / "__init__.py").write_text("", encoding="utf-8")
    (app_root / "__main__.py").write_text("from app.cli.main import main\n", encoding="utf-8")
    (app_root / "cli/__init__.py").write_text("", encoding="utf-8")
    (app_root / "cli/commands/__init__.py").write_text("", encoding="utf-8")
    (app_root / "cli/main.py").write_text(
        "import importlib\n"
        "_HANDLERS = {'run': ('app.cli.commands.run', 'cmd_run')}\n"
        "MESSAGE = 'app.dead'\n"
        "def main():\n"
        "    module, symbol = _HANDLERS['run']\n"
        "    return getattr(importlib.import_module(module), symbol)\n",
        encoding="utf-8",
    )
    (app_root / "cli/commands/run.py").write_text("def cmd_run(): pass\n", encoding="utf-8")
    (app_root / "dead.py").write_text("VALUE = 1\n", encoding="utf-8")

    assert _find_unreachable_production_modules(app_root) == {"app.dead"}


def test_python_production_reachability_follows_registered_factory_imports(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "__init__.py").write_text("", encoding="utf-8")
    (app_root / "__main__.py").write_text("from app.factory import build\n", encoding="utf-8")
    (app_root / "factory.py").write_text(
        "def _build():\n"
        "    from app.implementation import Implementation\n"
        "    return Implementation()\n"
        "def _dead():\n"
        "    from app.dead import VALUE\n"
        "    return VALUE\n"
        "_FACTORIES = {'implementation': _build}\n"
        "def build(name):\n"
        "    return _FACTORIES[name]()\n",
        encoding="utf-8",
    )
    (app_root / "implementation.py").write_text("class Implementation: pass\n", encoding="utf-8")
    (app_root / "dead.py").write_text("VALUE = 1\n", encoding="utf-8")

    assert _find_unreachable_production_modules(app_root) == {"app.dead"}
