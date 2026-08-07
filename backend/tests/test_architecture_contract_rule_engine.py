from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from architecture_contracts.catalog import RULES  # noqa: E402
from architecture_contracts.ipc_checks import (  # noqa: E402
    ManifestCommand,
    RustCommandSignature,
    diff_command_surface,
    diff_command_types,
)
from architecture_contracts.python_checks import (  # noqa: E402
    _check_backend_package_cycles,
    _check_typed_ndjson_error_emission,
)
from architecture_contracts.rust_checks import (  # noqa: E402
    _RUST_PUBLIC_MODEL_EXPORTS,
    _check_rust_lifecycle_result_handling,
    _check_rust_package_cycles,
    _check_rust_public_surface,
    _check_rust_reaper_ownership,
    _check_rust_submodule_cycles,
    _check_rust_task_adapter_boundaries,
    _check_rust_unused_dependencies,
)
from architecture_contracts.rules import (  # noqa: E402
    AbsentPathRule,
    ContractParseError,
    ForbiddenPatternRule,
    ForbiddenReferenceRule,
    RequiredPatternRule,
    run_rules,
)


def _write_exact_rust_public_api(root: Path, *, extra_config_exports: set[str] | None = None) -> Path:
    rust = root / "frontend/src-tauri/src"
    models = rust / "models"
    models.mkdir(parents=True)
    (rust / "lib.rs").write_text("pub mod models;\npub fn run() {\n}\n", encoding="utf-8")
    config_exports = sorted(_RUST_PUBLIC_MODEL_EXPORTS["config"] | (extra_config_exports or set()))
    (models / "mod.rs").write_text(
        "pub mod config {\n"
        "    pub use super::boundary::{\n" + ",\n".join(config_exports) + ",\n    };\n}\n"
        "pub mod task {\n"
        "    pub use super::boundary::{\n" + ",\n".join(sorted(_RUST_PUBLIC_MODEL_EXPORTS["task"])) + ",\n    };\n}\n",
        encoding="utf-8",
    )
    return rust


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


def test_rust_tasks_submodule_cycle_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    source.mkdir(parents=True)
    (source / "mod.rs").write_text("mod first;\nmod second;\n", encoding="utf-8")
    (source / "first.rs").write_text(
        "#[cfg(test)]\nmod tests {}\nuse crate::tasks::second::Value;\n",
        encoding="utf-8",
    )
    (source / "second.rs").write_text("use crate::tasks::first::Value;\n", encoding="utf-8")

    assert _check_rust_submodule_cycles(tmp_path, "tasks") == [
        "Rust tasks submodule dependency cycle: first -> second -> first"
    ]


def test_rust_task_tauri_imports_are_limited_to_composition_adapters(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    source.mkdir(parents=True)
    (source / "commands.rs").write_text("use tauri::State;\n", encoding="utf-8")
    (source / "spawn.rs").write_text("use tauri::AppHandle;\n", encoding="utf-8")
    (source / "tauri_ports.rs").write_text("use tauri::Emitter;\n", encoding="utf-8")
    (source / "ports.rs").write_text("use tauri::Emitter;\n", encoding="utf-8")
    (source / "controller.rs").write_text(
        "#[cfg(test)]\nmod tests {}\nuse tauri::Manager;\n",
        encoding="utf-8",
    )
    (source / "readers.rs").write_text("use tokio::io::AsyncRead;\n", encoding="utf-8")

    assert _check_rust_task_adapter_boundaries(tmp_path) == [
        "Rust task core imports Tauri outside the composition adapters: frontend/src-tauri/src/tasks/controller.rs",
        "Rust task core imports Tauri outside the composition adapters: frontend/src-tauri/src/tasks/ports.rs",
    ]


def test_rust_lifecycle_results_cannot_be_silenced_with_underscore_bindings(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    process_control = tmp_path / "frontend/src-tauri/src/process_control"
    source.mkdir(parents=True)
    process_control.mkdir()
    (source / "controller.rs").write_text(
        "async fn unsafe_cleanup(lifecycle: &Lifecycle, sink: &Sink, ticket: &mut Ticket) {\n"
        "    let _entered = lifecycle.begin_reaping().await;\n"
        "    sink.emit(event);\n"
        "    ticket.wait().await;\n"
        "    rollback_suspended_threads(items);\n"
        "}\n",
        encoding="utf-8",
    )

    assert _check_rust_lifecycle_result_handling(tmp_path) == [
        "Rust lifecycle/process result is explicitly ignored (`begin_reaping`): "
        "frontend/src-tauri/src/tasks/controller.rs:2",
        "Rust lifecycle/process result is explicitly ignored (`emit`): frontend/src-tauri/src/tasks/controller.rs:3",
        "Rust lifecycle/process result is explicitly ignored (`wait`): frontend/src-tauri/src/tasks/controller.rs:4",
        "Rust lifecycle/process result is explicitly ignored (`rollback_suspended_threads`): "
        "frontend/src-tauri/src/tasks/controller.rs:5",
    ]


def test_rust_lifecycle_result_gate_accepts_checked_outcomes(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    process_control = tmp_path / "frontend/src-tauri/src/process_control"
    source.mkdir(parents=True)
    process_control.mkdir()
    (source / "controller.rs").write_text(
        "async fn safe_cleanup(lifecycle: &Lifecycle, sink: &Sink, ticket: &mut Ticket) {\n"
        "    if !lifecycle.begin_reaping().await { return; }\n"
        "    if let Err(error) = sink.emit(event) { report(error); }\n"
        "    match ticket.wait().await { Reaped => {}, Failed(error) => report(error) }\n"
        "    let rollback = rollback_suspended_threads(items); consume(rollback);\n"
        "}\n",
        encoding="utf-8",
    )

    assert _check_rust_lifecycle_result_handling(tmp_path) == []


def test_rust_process_owner_may_only_be_detached_by_ticket_adapter(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    source.mkdir(parents=True)
    (source / "controller.rs").write_text(
        "fn detach(mut child: Child) {\n    tokio::spawn(async move { child.terminate_and_reap().await; });\n}\n",
        encoding="utf-8",
    )

    assert _check_rust_reaper_ownership(tmp_path) == [
        "Rust process owner is reaped by a fire-and-forget task outside subprocess.rs: "
        "frontend/src-tauri/src/tasks/controller.rs:2"
    ]


def test_rust_process_owner_helper_cannot_hide_detached_cleanup(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    source.mkdir(parents=True)
    (source / "cleanup.rs").write_text(
        "async fn cleanup_child(mut child: Child) {\n    child.terminate_and_reap().await;\n}\n",
        encoding="utf-8",
    )
    (source / "controller.rs").write_text(
        "fn detach(child: Child) {\n    tokio::spawn(cleanup_child(child));\n}\n",
        encoding="utf-8",
    )

    assert _check_rust_reaper_ownership(tmp_path) == [
        "Rust process owner is reaped by a fire-and-forget task outside subprocess.rs: "
        "frontend/src-tauri/src/tasks/controller.rs:2"
    ]


def test_rust_process_owner_helper_allows_a_retained_cleanup_handle(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    source.mkdir(parents=True)
    (source / "cleanup.rs").write_text(
        "async fn cleanup_child(mut child: Child) {\n    child.terminate_and_reap().await;\n}\n",
        encoding="utf-8",
    )
    (source / "controller.rs").write_text(
        "fn retain(child: Child) -> JoinHandle<()> {\n"
        "    let observer = tokio::spawn(cleanup_child(child));\n"
        "    observer\n"
        "}\n",
        encoding="utf-8",
    )

    assert _check_rust_reaper_ownership(tmp_path) == []


def test_rust_process_owner_helper_rejects_an_underscore_handle(tmp_path: Path) -> None:
    source = tmp_path / "frontend/src-tauri/src/tasks"
    source.mkdir(parents=True)
    (source / "cleanup.rs").write_text(
        "async fn cleanup_child(mut child: Child) { child.terminate_and_reap().await; }\n",
        encoding="utf-8",
    )
    (source / "controller.rs").write_text(
        "fn detach(child: Child) {\n    let _observer = tokio::spawn(cleanup_child(child));\n}\n",
        encoding="utf-8",
    )

    assert _check_rust_reaper_ownership(tmp_path) == [
        "Rust process owner is reaped by a fire-and-forget task outside subprocess.rs: "
        "frontend/src-tauri/src/tasks/controller.rs:2"
    ]


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


def test_renamed_rust_dependency_uses_the_local_crate_name(tmp_path: Path) -> None:
    crate = tmp_path / "frontend/src-tauri"
    source = crate / "src"
    source.mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[dependencies]\njson = { package = "serde_json", version = "1" }\n',
        encoding="utf-8",
    )
    (crate / "build.rs").write_text("", encoding="utf-8")
    (source / "lib.rs").write_text("fn encode(value: json::Value) { drop(value); }\n", encoding="utf-8")

    assert _check_rust_unused_dependencies(tmp_path) == []


def test_typify_pattern_runtime_dependency_requires_exact_schema_evidence(tmp_path: Path) -> None:
    crate = tmp_path / "frontend/src-tauri"
    source = crate / "src/models"
    contracts = tmp_path / "contracts"
    source.mkdir(parents=True)
    contracts.mkdir()
    (crate / "Cargo.toml").write_text(
        '[dependencies]\ntypify = "0.7"\nregress = "0.11"\n',
        encoding="utf-8",
    )
    (crate / "build.rs").write_text("", encoding="utf-8")
    (source / "mod.rs").write_text(
        'typify::import_types!(schema = "../../contracts/boundary.schema.json");\n',
        encoding="utf-8",
    )
    schema_path = contracts / "boundary.schema.json"
    schema_path.write_text('{"type":"string","pattern":"\\\\S"}\n', encoding="utf-8")

    assert _check_rust_unused_dependencies(tmp_path) == []

    schema_path.write_text('{"type":"string"}\n', encoding="utf-8")
    assert _check_rust_unused_dependencies(tmp_path) == [
        "unused Rust Cargo dependency `regress`: frontend/src-tauri/Cargo.toml"
    ]


def test_rust_public_surface_rejects_internal_public_item(tmp_path: Path) -> None:
    rust = _write_exact_rust_public_api(tmp_path)
    source = rust / "tasks/worker.rs"
    source.parent.mkdir(parents=True)
    source.write_text("pub fn leaked() {}\npub(crate) fn internal() {}\n", encoding="utf-8")
    assert _check_rust_public_surface(tmp_path) == [
        "Rust crate-internal source exposes a public item: frontend/src-tauri/src/tasks/worker.rs"
    ]


def test_rust_public_surface_requires_existing_exact_api_files(tmp_path: Path) -> None:
    rust = tmp_path / "frontend/src-tauri/src"
    rust.mkdir(parents=True)
    (rust / "lib.rs").write_text("pub mod models;\npub fn run(argument: bool) { drop(argument); }\n", encoding="utf-8")

    assert _check_rust_public_surface(tmp_path) == [
        "Rust public API allowlist path does not exist: frontend/src-tauri/src/models/mod.rs",
        "Rust crate public API drifted: missing=['pub fn run() {'], "
        "unexpected=['pub fn run(argument: bool) { drop(argument); }']",
    ]


def test_rust_public_surface_rejects_non_schema_model_export(tmp_path: Path) -> None:
    _write_exact_rust_public_api(tmp_path, extra_config_exports={"InternalCacheEntry"})

    assert _check_rust_public_surface(tmp_path) == [
        "Rust models `config` public schema drifted: missing=[], unexpected=['InternalCacheEntry']"
    ]


def test_typed_ndjson_check_rejects_duplicate_manual_error_envelopes(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/__main__.py"
    source.parent.mkdir(parents=True)
    source.write_text('A = {"type": "error"}\nB = {"type": "error"}\n', encoding="utf-8")
    assert _check_typed_ndjson_error_emission(tmp_path)
