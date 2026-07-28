from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from architecture_contracts.catalog import RULES  # noqa: E402
from architecture_contracts.checks import (  # noqa: E402
    ManifestCommand,
    RustCommandSignature,
    _check_backend_package_cycles,
    _check_rust_package_cycles,
    _check_rust_public_surface,
    _check_rust_unused_dependencies,
    _check_typed_ndjson_error_emission,
    diff_command_surface,
    diff_command_types,
)
from architecture_contracts.rules import (  # noqa: E402
    AbsentPathRule,
    ContractParseError,
    ForbiddenPatternRule,
    ForbiddenReferenceRule,
    RequiredPatternRule,
    run_rules,
)


@pytest.mark.parametrize(
    ("rule", "source", "expected"),
    [
        (
            ForbiddenPatternRule("dead", "source.py", r"obsolete", "dead code"),
            "obsolete()\n",
            ["dead code: source.py"],
        ),
        (
            ForbiddenPatternRule("dead", "source.py", r"obsolete", "dead code"),
            "supported()\n",
            [],
        ),
        (
            RequiredPatternRule("required", "source.py", r"supported", "missing boundary"),
            "supported()\n",
            [],
        ),
    ],
)
def test_pattern_rules(
    rule: ForbiddenPatternRule | RequiredPatternRule, source: str, expected: list[str], tmp_path: Path
) -> None:
    (tmp_path / "source.py").write_text(source, encoding="utf-8")
    assert run_rules(tmp_path, [rule]) == expected


def test_missing_source_is_a_parse_error(tmp_path: Path) -> None:
    rule = RequiredPatternRule("required", "missing.py", "value", "missing")
    with pytest.raises(ContractParseError, match="missing file"):
        rule.check(tmp_path)


def test_absent_path_rule(tmp_path: Path) -> None:
    (tmp_path / "obsolete.py").write_text("", encoding="utf-8")
    rule = AbsentPathRule("obsolete", "obsolete.py", "obsolete module")
    assert rule.check(tmp_path) == ["obsolete module: obsolete.py"]


def test_forbidden_reference_honors_excludes(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "bad.py").write_text("from app.algorithms import value\n", encoding="utf-8")
    (source / "allowed.py").write_text("from app.algorithms import value\n", encoding="utf-8")
    rule = ForbiddenReferenceRule(
        "direction",
        roots=("src",),
        patterns=(r"app\.algorithms\b",),
        message="dependency inversion",
        suffixes=(".py",),
        excludes=("src/allowed.py",),
    )
    assert rule.check(tmp_path) == ["dependency inversion: src/bad.py"]


def test_catalog_contains_only_current_invariant_rules() -> None:
    ids = [rule.rule_id for rule in RULES]
    assert len(ids) == len(set(ids))
    assert all(isinstance(rule, (AbsentPathRule, ForbiddenReferenceRule)) for rule in RULES)


def test_command_surface_diff_checks_names_and_arguments() -> None:
    issues = diff_command_surface(
        manifest={"start_task", "control_task"},
        permissions={"start_task", "control_task"},
        rust_args={"start_task": {"request"}, "control_task": {"kind"}},
        handlers={"start_task", "control_task"},
        invoke_args={"start_task", "control_task"},
        contract_args={"start_task": {"request"}, "control_task": {"wrong"}},
    )
    assert issues == ["IPC command args drift for `control_task`: rust=['kind'], contract=['wrong']"]


def test_command_type_diff_checks_manifest_arguments_and_results() -> None:
    issues = diff_command_types(
        {
            "inspect_video": ManifestCommand(
                args={"inputPath": "string"},
                result="VideoInfo",
            )
        },
        {
            "inspect_video": RustCommandSignature(
                args={"inputPath": "PathBuf"},
                result="Option<VideoInfo>",
            )
        },
    )

    assert issues == [
        "IPC command type drift for `inspect_video.inputPath`: manifest=String, rust=PathBuf",
        "IPC command result drift for `inspect_video`: manifest=VideoInfo, rust=Option<VideoInfo>",
    ]


def test_backend_package_cycle_is_reported(tmp_path: Path) -> None:
    app = tmp_path / "backend/app"
    (app / "planning").mkdir(parents=True)
    (app / "processing").mkdir()
    (app / "planning/a.py").write_text("from app.processing import b\n", encoding="utf-8")
    (app / "processing/b.py").write_text("from app.planning import a\n", encoding="utf-8")
    assert _check_backend_package_cycles(tmp_path) == [
        "backend package dependency cycle: planning -> processing -> planning"
    ]


def test_backend_package_dag_is_accepted(tmp_path: Path) -> None:
    app = tmp_path / "backend/app"
    (app / "planning").mkdir(parents=True)
    (app / "protocol").mkdir()
    (app / "planning/a.py").write_text("from app.protocol import payloads\n", encoding="utf-8")
    (app / "protocol/payloads.py").write_text("", encoding="utf-8")
    assert _check_backend_package_cycles(tmp_path) == []


def test_rust_package_cycle_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src"
    (source / "tasks").mkdir(parents=True)
    (source / "runtime").mkdir()
    (source / "lib.rs").write_text("mod tasks;\nmod runtime;\n", encoding="utf-8")
    (source / "tasks/mod.rs").write_text("use crate::runtime::Paths;\n", encoding="utf-8")
    (source / "runtime/mod.rs").write_text("use crate::tasks::Task;\n", encoding="utf-8")

    assert _check_rust_package_cycles(tmp_path) == ["Rust package dependency cycle: runtime -> tasks -> runtime"]


def test_unused_rust_dependency_is_reported(tmp_path: Path) -> None:
    crate = tmp_path / "frontend/src-tauri"
    source = crate / "src"
    source.mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[dependencies]\nserde = "1"\nunused-crate = "1"\n',
        encoding="utf-8",
    )
    (crate / "build.rs").write_text("", encoding="utf-8")
    (source / "lib.rs").write_text("fn encode<T: serde::Serialize>(_value: T) {}\n", encoding="utf-8")

    assert _check_rust_unused_dependencies(tmp_path) == [
        "unused Rust Cargo dependency `unused-crate`: frontend/src-tauri/Cargo.toml"
    ]


def test_rust_public_surface_rejects_internal_public_item(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks/worker.rs"
    source.parent.mkdir(parents=True)
    source.write_text("pub fn leaked() {}\npub(crate) fn internal() {}\n", encoding="utf-8")
    assert _check_rust_public_surface(tmp_path) == [
        "Rust crate-internal source exposes a public item: frontend/src-tauri/src/tasks/worker.rs"
    ]


def test_typed_ndjson_check_rejects_duplicate_manual_error_envelopes(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/__main__.py"
    source.parent.mkdir(parents=True)
    source.write_text('A = {"type": "error"}\nB = {"type": "error"}\n', encoding="utf-8")
    assert _check_typed_ndjson_error_emission(tmp_path)
