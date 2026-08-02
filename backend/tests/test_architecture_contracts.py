"""Integration tests for repository architecture contracts."""

from __future__ import annotations

import builtins
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from architecture_contracts.application_defaults import (  # noqa: E402
    _REQUIRED_CONSUMERS,
    check_application_default_consumers,
)
from architecture_contracts.checks import collect_architecture_issues  # noqa: E402
from architecture_contracts.filter_contracts import check_filter_contract_consumers  # noqa: E402
from architecture_contracts.ipc_checks import (  # noqa: E402
    _collect_manifest_commands,
    diff_command_surface,
)
from architecture_contracts.model_assets import (  # noqa: E402
    _REQUIRED_MODEL_ASSET_CONSUMERS,
    check_model_asset_consumers,
)
from architecture_contracts.protocol_markers import check_protocol_marker_literals  # noqa: E402
from architecture_contracts.python_checks import (  # noqa: E402
    _check_python_algorithm_factory_registry,
    _check_python_boundary_field_consumers,
    _check_python_cli_commands,
    _check_python_package_reexports,
    _check_paddlegan_metadata,
    _check_side_effect_free_python_packages,
    _collect_python_name_registry,
    _find_unconsumed_python_boundary_fields,
    _find_unconsumed_python_module_exports,
    _find_unconsumed_python_package_reexports,
    diff_paddlegan_catalog_contract,
)
from architecture_contracts.rules import ContractParseError  # noqa: E402
from architecture_contracts.rust_checks import (  # noqa: E402
    _check_rust_unused_dependencies,
    _find_unconsumed_rust_model_reexports,
)
from architecture_contracts.rust_visibility import check_rust_restricted_visibility  # noqa: E402
from architecture_contracts.rust_source import production_rust_source  # noqa: E402
from architecture_contracts.script_reachability import check_script_reachability  # noqa: E402
from architecture_contracts.typescript_checks import (  # noqa: E402
    _check_frontend_dependency_boundaries,
    _check_frontend_test_layout,
    _find_unconsumed_protocol_reexports,
    _find_unconsumed_test_support_exports,
    _find_unconsumed_test_ids,
    _find_unreferenced_css_classes,
    _find_unused_css_custom_properties,
)


def _write_application_default_fixture(root: Path) -> None:
    defaults = json.loads((REPO_ROOT / "contracts/application-defaults.json").read_text(encoding="utf-8"))
    contract = root / "contracts/application-defaults.json"
    contract.parent.mkdir(parents=True)
    contract.write_text(json.dumps(defaults), encoding="utf-8")
    for path_name, marker in _REQUIRED_CONSUMERS.items():
        path = root / path_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker, encoding="utf-8")


def _write_model_asset_fixture(root: Path) -> None:
    contract = root / "contracts/model-assets.json"
    contract.parent.mkdir(parents=True)
    contract.write_text((REPO_ROOT / "contracts/model-assets.json").read_text(encoding="utf-8"), encoding="utf-8")
    for path_name, marker in _REQUIRED_MODEL_ASSET_CONSUMERS.items():
        path = root / path_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker, encoding="utf-8")


def test_application_default_gate_rejects_a_reintroduced_product_literal(tmp_path: Path) -> None:
    _write_application_default_fixture(tmp_path)

    assert check_application_default_consumers(tmp_path) == []

    workflow = tmp_path / "frontend/src/services/preset/workflow-defaults.ts"
    workflow.write_text("APPLICATION_DEFAULTS\nconst model = '4.25'\n", encoding="utf-8")
    issues = check_application_default_consumers(tmp_path)
    assert len(issues) == 1
    assert "hard-coded instead of generated" in issues[0]


def test_application_default_gate_scans_semantic_filter_fallbacks_outside_known_consumers(tmp_path: Path) -> None:
    _write_application_default_fixture(tmp_path)

    backend = tmp_path / "backend/app/processing/rogue.py"
    backend.parent.mkdir(parents=True, exist_ok=True)
    backend.write_text('value = params.get("amount", 0.5)\n', encoding="utf-8")
    frontend = tmp_path / "frontend/src/components/Rogue.vue"
    frontend.parent.mkdir(parents=True, exist_ok=True)
    frontend.write_text('<script setup lang="ts">const value = params.factor ?? 0.5</script>\n', encoding="utf-8")

    issues = check_application_default_consumers(tmp_path)
    assert any("semantic filter default fallback" in issue and "rogue.py" in issue for issue in issues)
    assert any("semantic filter default fallback" in issue and "Rogue.vue" in issue for issue in issues)


def test_model_asset_gate_rejects_a_mirrored_hash(tmp_path: Path) -> None:
    _write_model_asset_fixture(tmp_path)
    assert check_model_asset_consumers(tmp_path) == []

    rogue = tmp_path / "backend/app/rogue.py"
    rogue.write_text(
        'MODEL_HASH = "19e06889ff7e96f3904c24562667949bb7e452ab02234508db51759741c91efb"\n',
        encoding="utf-8",
    )
    assert check_model_asset_consumers(tmp_path) == [
        "model asset literal is mirrored outside generated bindings: backend/app/rogue.py"
    ]


def test_filter_constraint_gate_rejects_hardcoded_bounds(tmp_path: Path) -> None:
    consumers = {
        "frontend/src/services/filters/filter-catalog.ts": "FILTER_FIELD_CONSTRAINTS",
        "frontend/src/services/filters/anime-cleanup.ts": "FILTER_FIELD_CONSTRAINTS",
        "frontend/src/components/filter-steps/FilterScale.vue": "FILTER_FIELD_CONSTRAINTS",
    }
    for path_name, source in consumers.items():
        path = tmp_path / path_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    assert check_filter_contract_consumers(tmp_path) == []

    scale = tmp_path / "frontend/src/components/filter-steps/FilterScale.vue"
    scale.write_text('FILTER_FIELD_CONSTRAINTS\n<input :min="1" />\n', encoding="utf-8")
    assert check_filter_contract_consumers(tmp_path) == [
        "filter constraint is hard-coded instead of generated: frontend/src/components/filter-steps/FilterScale.vue:2"
    ]


def test_script_reachability_follows_python_imports_and_powershell_dot_sources(tmp_path: Path) -> None:
    pre_commit = tmp_path / ".pre-commit-config.yaml"
    pre_commit.write_text(
        "entry: python scripts/main.py\nentry: pwsh scripts/main.ps1\n",
        encoding="utf-8",
    )
    scripts = tmp_path / "scripts"
    package = scripts / "helpers"
    package.mkdir(parents=True)
    (scripts / "main.py").write_text("from helpers import worker\n", encoding="utf-8")
    (package / "__init__.py").write_text("\n", encoding="utf-8")
    (package / "worker.py").write_text("VALUE = 1\n", encoding="utf-8")
    (scripts / "main.ps1").write_text(
        '. (Join-Path $PSScriptRoot "runtime-tools.ps1")\n',
        encoding="utf-8",
    )
    (scripts / "runtime-tools.ps1").write_text("function Invoke-Tool {}\n", encoding="utf-8")
    (scripts / "orphan.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert check_script_reachability(tmp_path) == ["unreachable repository script: scripts/orphan.py"]


def test_restricted_rust_visibility_requires_a_non_test_consumer(tmp_path: Path) -> None:
    rust = tmp_path / "frontend/src-tauri/src"
    rust.mkdir(parents=True)
    (rust / "worker.rs").write_text(
        "pub(crate) fn used() {}\npub(super) fn orphan() {}\npub(crate) fn caller() { used(); }\n",
        encoding="utf-8",
    )

    assert check_rust_restricted_visibility(tmp_path) == [
        "restricted Rust symbol has no cross-module production consumer: frontend/src-tauri/src/worker.rs:1 `used`",
        "restricted Rust symbol has no cross-module production consumer: frontend/src-tauri/src/worker.rs:2 `orphan`",
        "restricted Rust symbol has no cross-module production consumer: frontend/src-tauri/src/worker.rs:3 `caller`",
    ]


def test_rust_visibility_resolves_qualified_paths_and_use_aliases(tmp_path: Path) -> None:
    rust = tmp_path / "frontend/src-tauri/src"
    rust.mkdir(parents=True)
    (rust / "worker.rs").write_text(
        "pub(crate) fn imported() {}\npub(crate) fn qualified() {}\n",
        encoding="utf-8",
    )
    (rust / "consumer.rs").write_text(
        "use crate::worker::imported as run;\nfn consume() { run(); crate::worker::qualified(); }\n",
        encoding="utf-8",
    )

    assert check_rust_restricted_visibility(tmp_path) == []


def test_rust_visibility_ignores_unrelated_same_names_and_test_only_uses(tmp_path: Path) -> None:
    rust = tmp_path / "frontend/src-tauri/src"
    rust.mkdir(parents=True)
    (rust / "worker.rs").write_text("pub(crate) fn orphan() {}\n", encoding="utf-8")
    (rust / "consumer.rs").write_text(
        "fn orphan() {}\n#[cfg(test)]\nuse crate::worker::orphan;\n",
        encoding="utf-8",
    )

    assert check_rust_restricted_visibility(tmp_path) == [
        "restricted Rust symbol has no cross-module production consumer: frontend/src-tauri/src/worker.rs:1 `orphan`"
    ]


def test_rust_production_source_removes_only_cfg_test_items() -> None:
    source = """#[cfg(test)]
use crate::TaskState;
pub(crate) fn production_after_import() {}
struct Session {
    value: usize,
    #[cfg(test)]
    test_handshake: Option<usize>,
}
#[cfg(test)]
mod tests {
    const MARKER: &str = "[VP_PROGRESS]";
}
pub(super) fn production_after_module() { production_after_import(); }
"""

    production = production_rust_source(source)

    assert "TaskState" not in production
    assert "test_handshake" not in production
    assert "mod tests" not in production
    assert "production_after_import" in production
    assert "production_after_module" in production
    assert production.count("\n") == source.count("\n")


def test_rust_visibility_scans_production_after_test_only_import(tmp_path: Path) -> None:
    rust = tmp_path / "frontend/src-tauri/src"
    rust.mkdir(parents=True)
    (rust / "worker.rs").write_text(
        "#[cfg(test)]\nuse crate::Fixture;\npub(crate) fn orphan_after_test_import() {}\n",
        encoding="utf-8",
    )

    assert check_rust_restricted_visibility(tmp_path) == [
        "restricted Rust symbol has no cross-module production consumer: "
        "frontend/src-tauri/src/worker.rs:3 `orphan_after_test_import`"
    ]


def test_rust_dev_dependency_usage_in_compile_fail_fixtures_is_counted(tmp_path: Path) -> None:
    crate = tmp_path / "frontend/src-tauri"
    (crate / "src").mkdir(parents=True)
    (crate / "tests/ui").mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "fixture"\nversion = "0.1.0"\nedition = "2021"\n[dev-dependencies]\ntrybuild = "1"\n',
        encoding="utf-8",
    )
    (crate / "src/lib.rs").write_text("pub fn production() {}\n", encoding="utf-8")
    fixture = crate / "tests/compile_fail.rs"
    fixture.write_text("fn check() { let _ = trybuild::TestCases::new(); }\n", encoding="utf-8")

    assert _check_rust_unused_dependencies(tmp_path) == []

    fixture.write_text("fn check() {}\n", encoding="utf-8")
    assert _check_rust_unused_dependencies(tmp_path) == [
        "unused Rust Cargo dev-dependency `trybuild`: frontend/src-tauri/Cargo.toml"
    ]


def test_manifest_command_reader_accepts_schema_version_five(tmp_path: Path) -> None:
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "ipc-manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 5,
                "commands": [
                    {"name": "start_task", "args": {"request": "TaskRequest"}, "result": "void"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert set(_collect_manifest_commands(tmp_path)) == {"start_task"}


def test_protocol_marker_gate_rejects_declared_and_unknown_literal_mirrors(tmp_path: Path) -> None:
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "ipc-manifest.json").write_text(
        json.dumps(
            {
                "protocolConstants": {
                    "terminalProgressPrefix": "[VP_PROGRESS]",
                    "stageWorkerEventPrefix": "VP_STAGE_EVENT ",
                    "tensorRtLogPrefix": "[VP_TRT]",
                }
            }
        ),
        encoding="utf-8",
    )
    backend = tmp_path / "backend/app"
    frontend = tmp_path / "frontend/src"
    rust = tmp_path / "frontend/src-tauri/src"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    rust.mkdir(parents=True)
    (backend / "consumer.py").write_text('PREFIX = "[VP_TRT]"\n', encoding="utf-8")
    (frontend / "consumer.ts").write_text("const prefix = '[VP_UNKNOWN]'\n", encoding="utf-8")
    (rust / "consumer.rs").write_text(
        '#[cfg(test)]\nconst TEST_ONLY: &str = "[VP_PROGRESS]";\nconst ENV: &str = "VP_RUNTIME_ROOT";\n',
        encoding="utf-8",
    )

    assert check_protocol_marker_literals(tmp_path) == [
        "hard-coded protocol marker `[VP_TRT]`: backend/app/consumer.py:1",
        "undeclared protocol marker `[VP_UNKNOWN]`: frontend/src/consumer.ts:1",
    ]


def test_frontend_dependency_boundaries_reject_protocol_submodule_import(tmp_path: Path) -> None:
    source_path = tmp_path / "frontend/src/services/example.ts"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("import { TASK_ERROR_CODES } from '@/types/protocol/errors'\n", encoding="utf-8")

    assert _check_frontend_dependency_boundaries(tmp_path) == [
        "protocol submodule import outside protocol layer: frontend/src/services/example.ts",
    ]


def test_protocol_reexport_check_reports_only_unconsumed_types() -> None:
    index_text = """
export type { Used } from '@/types/generated/Used'
export type { Aliased } from '@/types/generated/Aliased'
export type { Relative } from '@/types/generated/Relative'
export type { Unused } from '@/types/generated/Unused'
"""
    consumers = [
        "import { computed } from 'vue'\nimport type { Used, Aliased as LocalAlias } from '@/types/protocol'\n",
        "import type { Relative } from '../protocol'\n",
    ]

    assert _find_unconsumed_protocol_reexports(index_text, consumers) == {"Unused"}


def test_rust_model_reexport_check_ignores_deep_imports() -> None:
    model_mod = """
pub use config::{Used, Dead};
pub use task::Qualified;
"""
    consumers = [
        "use crate::models::{Used as LocalUsed};\n",
        "let _: crate::models::Qualified;\n",
        "use crate::models::config::Dead;\n",
    ]

    assert _find_unconsumed_rust_model_reexports(model_mod, consumers) == {"Dead"}


def test_global_css_check_reports_only_unreferenced_classes() -> None:
    css = ".used { color: red; }\n.dead, .also-used:hover { color: blue; }\n"
    consumers = ['<div class="used also-used"></div>']

    assert _find_unreferenced_css_classes(css, consumers) == {"dead"}


def test_global_css_check_reports_only_unused_custom_properties() -> None:
    css = ":root { --used: red; --dead: blue; }\n.example { color: var(--used); }\n"

    assert _find_unused_css_custom_properties(css, [css]) == {"--dead"}


def test_test_id_check_reports_only_unconsumed_hooks() -> None:
    sources = ['<div data-testid="used"></div>', '<div data-testid="dead"></div>']
    tests = ["await $('[data-testid=\"used\"]')"]

    assert _find_unconsumed_test_ids(sources, tests) == {"dead"}


def test_test_support_export_check_ignores_specs_and_reports_unused_helpers() -> None:
    sources = {
        "frontend/tests/e2e/helpers.ts": "export const used = 1\nexport interface Dead {}\n",
        "frontend/tests/e2e/example.spec.ts": "export const specLocal = used\n",
    }

    assert _find_unconsumed_test_support_exports(sources) == [
        ("frontend/tests/e2e/helpers.ts", "Dead"),
    ]


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
        handlers={"check_environment", "obsolete_handler"},
        invoke_args={"check_environment", "obsolete"},
        contract_args={"check_environment": set(), "start_task": {"payload"}},
    )

    assert any("permissions" in issue and "start_task" in issue for issue in issues)
    assert any("handlers" in issue and "obsolete_handler" in issue for issue in issues)
    assert any("frontend" in issue and "obsolete" in issue for issue in issues)
    assert any("args drift" in issue and "start_task" in issue for issue in issues)


def test_paddlegan_contract_diff_reports_catalog_and_descriptor_drift() -> None:
    issues = diff_paddlegan_catalog_contract(
        {"edvr", "basicvsr"},
        {"basicvsr", "extra"},
        {"execution_mode": "single"},
    )

    assert any("missing-factories=['edvr']" in issue for issue in issues)
    assert any("extra-factories=['extra']" in issue for issue in issues)
    assert any("descriptor fields drift" in issue for issue in issues)


def test_paddlegan_contract_accepts_geometry_policy_descriptor() -> None:
    descriptor = {
        "execution_mode": "sequence",
        "requires_file_pipeline": True,
        "geometry": {"kind": "fixed_scale", "fixed_scale_factor": 4.0},
        "supported_backends": frozenset({"paddle"}),
        "factory_key": "paddlegan_vsr",
        "model_kind": "paddlegan_vsr",
    }

    assert (
        diff_paddlegan_catalog_contract(
            {"edvr"},
            {"edvr"},
            descriptor,
        )
        == []
    )


def test_python_factory_registry_requires_literal_local_function_targets() -> None:
    assert _collect_python_name_registry("_FACTORIES = {'rife': _build_rife}\n", "_FACTORIES") == {
        "rife": "_build_rife"
    }

    with pytest.raises(ContractParseError, match="local factory functions"):
        _collect_python_name_registry("_FACTORIES = {'rife': 'app.rife'}\n", "_FACTORIES")


def test_python_boundary_field_check_ignores_test_only_consumers() -> None:
    declarations = {
        "backend/app/catalog/example.py": (
            "from dataclasses import dataclass\n"
            "@dataclass(frozen=True)\n"
            "class Descriptor:\n"
            "    used: str\n"
            "    test_only: str\n"
        )
    }
    production = {
        "backend/app/consumer.py": (
            "from app.catalog.example import Descriptor\n"
            "class Unrelated:\n"
            "    test_only: str\n"
            "def consume(descriptor: Descriptor, unrelated: Unrelated):\n"
            "    return descriptor.used, unrelated.test_only\n"
        )
    }
    tests = {
        "backend/tests/test_consumer.py": (
            "from app.catalog.example import Descriptor\n"
            "def test_value(descriptor: Descriptor):\n"
            "    assert descriptor.test_only\n"
        )
    }

    assert _find_unconsumed_python_boundary_fields(declarations, {**production, **tests}) == []
    assert _find_unconsumed_python_boundary_fields(declarations, production) == [
        ("backend/app/catalog/example.py", "Descriptor", "test_only"),
    ]


def test_python_package_reexport_check_requires_production_import() -> None:
    package = "app.example"
    init_text = "from app.example.owner import Used, TestOnly\n__all__ = ['Used', 'TestOnly']\n"
    production = ["from app.example import Used\n"]
    tests = ["from app.example import TestOnly\n"]

    assert _find_unconsumed_python_package_reexports(package, init_text, [*production, *tests]) == set()
    assert _find_unconsumed_python_package_reexports(package, init_text, production) == {"TestOnly"}


def test_python_module_export_check_ignores_self_all_and_test_only_consumers() -> None:
    module = "app.example.owner"
    source = "def used():\n    return 1\ndef test_only():\n    return 2\n__all__ = ['used', 'test_only']\n"
    production = [("app.consumer", False, "from app.example.owner import used\nused()\n")]
    tests = [("tests.test_owner", False, "from app.example.owner import test_only\ntest_only()\n")]

    assert _find_unconsumed_python_module_exports(module, source, [*production, *tests]) == set()
    assert _find_unconsumed_python_module_exports(module, source, production) == {"test_only"}


def test_python_command_and_side_effect_checks_cover_current_repository() -> None:
    assert _check_python_cli_commands(REPO_ROOT) == []
    assert _check_python_algorithm_factory_registry(REPO_ROOT) == []
    assert _check_side_effect_free_python_packages(REPO_ROOT) == []
    assert _check_python_boundary_field_consumers(REPO_ROOT) == []
    assert _check_python_package_reexports(REPO_ROOT) == []


def test_paddlegan_architecture_check_never_imports_runtime_modules(monkeypatch) -> None:
    original_import = builtins.__import__

    def reject_runtime_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "app" or name.startswith("app."):
            raise AssertionError(f"architecture check imported runtime module {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", reject_runtime_import)

    assert _check_paddlegan_metadata(REPO_ROOT) == []


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
