"""Contract generation orchestration and CLI."""

from __future__ import annotations

import argparse
import difflib
import sys
import tempfile
from pathlib import Path

from .application_defaults import (
    load_application_defaults,
    render_filter_constraints_typescript,
    render_python_application_defaults,
    render_rust_application_defaults,
    render_typescript_application_defaults,
)
from .context import CONTRACTS, ROOT
from .model_assets import load_model_assets, render_python_model_assets, render_rust_model_assets
from .python_renderer import (
    _generate_python_contracts,
    _render_python_bootstrap_constants,
    _render_python_protocol_constants,
)
from .rust_command_renderer import _render_rust_manifest, _render_rust_oneshot_contracts
from .rust_renderer import (
    _render_rust_error_code_conversion,
    _render_rust_events,
    _render_rust_generated_mod,
    _render_rust_persistence_versions,
    _render_rust_task_envelopes,
)
from .schema_composition import (
    _render_boundary_schema,
    _render_ndjson_schema,
    _render_stage_worker_schema,
    _render_typescript_boundary_schema,
)
from .typescript_renderer import _generate_typescript, _render_ipc_contract, _render_typescript_events
from .validation import validate_contracts


def _compare_or_write(target: Path, generated: Path | str, *, check: bool) -> bool:
    content = generated.read_text(encoding="utf-8") if isinstance(generated, Path) else generated
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    if current == content:
        return True
    if check:
        diff = difflib.unified_diff(
            current.splitlines(),
            content.splitlines(),
            fromfile=str(target.relative_to(ROOT)),
            tofile="generated",
            lineterm="",
        )
        sys.stderr.write("\n".join(diff) + "\n")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of updating stale generated files")
    args = parser.parse_args()
    manifest = validate_contracts()
    model_assets = load_model_assets(CONTRACTS)
    application_defaults = load_application_defaults(CONTRACTS, model_assets)

    with tempfile.TemporaryDirectory(prefix="vp-contracts-") as temp:
        temp_dir = Path(temp)
        boundary_output = temp_dir / "boundary.schema.json"
        boundary_output.write_text(_render_boundary_schema(), encoding="utf-8", newline="\n")
        python_output = temp_dir / "contracts.py"
        stage_worker_schema = temp_dir / "stage-worker.schema.json"
        stage_worker_schema.write_text(_render_stage_worker_schema(model_assets), encoding="utf-8", newline="\n")
        stage_worker_output = temp_dir / "stage_worker_contracts.py"
        typescript_schema_dir = temp_dir / "typescript"
        typescript_schema_dir.mkdir()
        typescript_schema = typescript_schema_dir / "boundary.schema.json"
        typescript_schema.write_text(_render_typescript_boundary_schema(), encoding="utf-8", newline="\n")
        typescript_output = temp_dir / "contracts.ts"
        _generate_python_contracts(boundary_output, python_output)
        _generate_python_contracts(stage_worker_schema, stage_worker_output, collapse_root_models=True)
        _generate_typescript(typescript_schema, typescript_output)
        outputs: tuple[tuple[Path, Path | str], ...] = (
            (
                ROOT / "backend/app/generated/application_defaults.py",
                render_python_application_defaults(application_defaults),
            ),
            (
                ROOT / "backend/app/generated/model_assets.py",
                render_python_model_assets(model_assets),
            ),
            (ROOT / "backend/app/generated/contracts.py", python_output),
            (ROOT / "backend/app/generated/stage_worker_contracts.py", stage_worker_output),
            (
                ROOT / "contracts/boundary.schema.json",
                boundary_output,
            ),
            (ROOT / "contracts/ndjson.schema.json", _render_ndjson_schema(manifest)),
            (
                ROOT / "frontend/src/types/generated/contracts.ts",
                typescript_output,
            ),
            (
                ROOT / "frontend/src/types/generated/application-defaults.ts",
                render_typescript_application_defaults(application_defaults),
            ),
            (
                ROOT / "frontend/src/types/generated/filter-constraints.ts",
                render_filter_constraints_typescript(CONTRACTS),
            ),
            (ROOT / "frontend/src/lib/ipc/contract.ts", _render_ipc_contract(manifest)),
            (
                ROOT / "frontend/src/types/protocol/events.ts",
                _render_typescript_events(manifest),
            ),
            (
                ROOT / "backend/app/generated/protocol_constants.py",
                _render_python_protocol_constants(manifest),
            ),
            (
                ROOT / "backend/app/generated/bootstrap_constants.py",
                _render_python_bootstrap_constants(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/ipc_manifest.rs",
                _render_rust_manifest(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/application_defaults.rs",
                render_rust_application_defaults(application_defaults),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/model_assets.rs",
                render_rust_model_assets(model_assets),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/backend_oneshot.rs",
                _render_rust_oneshot_contracts(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/models/generated_error_codes.rs",
                _render_rust_error_code_conversion(),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/backend_task_envelope.rs",
                _render_rust_task_envelopes(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/task_events.rs",
                _render_rust_events(manifest),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/persistence_versions.rs",
                _render_rust_persistence_versions(),
            ),
            (
                ROOT / "frontend/src-tauri/src/generated/mod.rs",
                _render_rust_generated_mod(manifest),
            ),
        )
        results = [_compare_or_write(target, generated, check=args.check) for target, generated in outputs]
        clean = all(results)
    return 0 if clean else 1
