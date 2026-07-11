"""Integration tests for repository architecture contracts."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from architecture_contracts.checks import (  # noqa: E402
    _check_frontend_test_layout,
    collect_architecture_issues,
    diff_command_surface,
    diff_paddlegan_vsr_contract,
)


def _load_checker_module():
    script_path = SCRIPTS_DIR / "check_architecture_contracts.py"
    spec = importlib.util.spec_from_file_location("architecture_checker_cli", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_repository_satisfies_architecture_contracts() -> None:
    assert collect_architecture_issues(REPO_ROOT) == []


def test_frontend_test_layout_rejects_specs_and_test_directories_in_source(tmp_path: Path) -> None:
    frontend_src = tmp_path / "frontend/src"
    (frontend_src / "components").mkdir(parents=True)
    (frontend_src / "services/__tests__").mkdir(parents=True)
    (frontend_src / "components/Example.spec.ts").write_text("", encoding="utf-8")

    issues = _check_frontend_test_layout(tmp_path)

    assert "frontend unit test outside tests/unit: frontend/src/components/Example.spec.ts" in issues
    assert "frontend __tests__ directory outside tests/unit: frontend/src/services/__tests__" in issues


def test_command_surface_diff_reports_membership_and_argument_drift() -> None:
    issues = diff_command_surface(
        manifest={"check_environment", "start_task"},
        permissions={"check_environment"},
        rust_args={"check_environment": set(), "start_task": {"request"}},
        invoke_args={"check_environment", "obsolete"},
        contract_args={"check_environment": set(), "start_task": {"payload"}},
    )

    assert any("permissions" in issue and "start_task" in issue for issue in issues)
    assert any("frontend" in issue and "obsolete" in issue for issue in issues)
    assert any("args drift" in issue and "start_task" in issue for issue in issues)


def test_paddlegan_contract_diff_reports_metadata_drift() -> None:
    issues = diff_paddlegan_vsr_contract(
        {"edvr", "basicvsr"},
        {
            "edvr": {
                "family": "paddlegan_vsr",
                "fixedScaleFactor": 2,
                "inputFrameMode": "editable_chunk",
            },
            "extra": {
                "family": "paddlegan_vsr",
                "fixedScaleFactor": 4,
                "inputFrameMode": "editable_chunk",
            },
        },
    )

    assert any("missing-metadata=['basicvsr']" in issue for issue in issues)
    assert any("extra-metadata=['extra']" in issue for issue in issues)
    assert any("fixedScaleFactor=4" in issue for issue in issues)
    assert any("fixed_window" in issue for issue in issues)


def test_architecture_checker_cli_preserves_success_protocol() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "check_architecture_contracts.py")],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "[check-architecture-contracts] OK\n"
    assert completed.stderr == ""


def test_architecture_checker_cli_reports_drift_with_exit_one(monkeypatch, capsys) -> None:
    module = _load_checker_module()
    monkeypatch.setattr(module, "collect_architecture_issues", lambda _root: ["broken boundary"])

    assert module.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "[check-architecture-contracts] DRIFT DETECTED:\n  - broken boundary\n"


def test_architecture_checker_cli_reports_parse_errors_with_exit_two(monkeypatch, capsys) -> None:
    module = _load_checker_module()

    def fail(_root):
        raise RuntimeError("invalid source")

    monkeypatch.setattr(module, "collect_architecture_issues", fail)

    assert module.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "[check-architecture-contracts] PARSE ERROR: invalid source\n"
