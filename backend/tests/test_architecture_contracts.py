"""Tests for repository architecture contract checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_architecture_contracts.py"
ALL_PADDLEGAN_VSR_MODELS = {
    "ppmsvsr",
    "ppmsvsr-large",
    "edvr",
    "basicvsr",
    "iconvsr",
    "basicvsr-plus-plus",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("check_architecture_contracts", SCRIPT_PATH)
    assert spec and spec.loader, "architecture contract script is not loadable"
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_architecture_contracts"] = module
    spec.loader.exec_module(module)
    return module


def test_paddlegan_vsr_contract_matches_current_repo() -> None:
    module = _load_module()
    backend_enabled = module._collect_backend_paddlegan_enabled_models()
    backend_disabled = module._collect_backend_paddlegan_disabled_models()
    frontend_models = module._collect_frontend_paddlegan_models()

    issues = module._diff_paddlegan_vsr_contract(backend_enabled, backend_disabled, frontend_models)

    assert backend_enabled == ALL_PADDLEGAN_VSR_MODELS
    assert backend_disabled == set()
    assert frontend_models == backend_enabled
    assert issues == []


def test_paddlegan_vsr_contract_flags_frontend_reexposing_disabled_model() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_enabled={"ppmsvsr", "edvr"},
        backend_disabled={"basicvsr"},
        frontend_models={"ppmsvsr", "edvr", "basicvsr"},
    )

    assert any("frontend" in issue.lower() and "basicvsr" in issue for issue in issues), issues
    assert any("disabled" in issue.lower() and "basicvsr" in issue for issue in issues), issues


def test_paddlegan_vsr_contract_flags_backend_frontend_drift() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_enabled={"ppmsvsr", "edvr"},
        backend_disabled=set(),
        frontend_models={"ppmsvsr"},
    )

    assert any("backend" in issue.lower() and "edvr" in issue for issue in issues), issues
