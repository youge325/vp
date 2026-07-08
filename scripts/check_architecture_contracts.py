#!/usr/bin/env python3
"""Architecture boundary checks for VP Workbench.

The checks are intentionally small and dependency-free so they can run from
pre-commit, CI, or a local shell before broader frontend/backend test suites.
They protect contracts that are easy to break through otherwise harmless
renames: the Tauri command surface, docs command names, generated-type import
boundaries, and direct IPC access from UI/store layers.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS_MANIFEST = ROOT / "frontend" / "src-tauri" / "src" / "commands_manifest.rs"
DEFAULT_PERMISSIONS = ROOT / "frontend" / "src-tauri" / "permissions" / "default.toml"
IPC_ENDPOINT_DIR = ROOT / "frontend" / "src" / "lib" / "ipc" / "endpoints"
IPC_CONTRACT = ROOT / "frontend" / "src" / "lib" / "ipc" / "contract.ts"
TAURI_SRC = ROOT / "frontend" / "src-tauri" / "src"
FRONTEND_SRC = ROOT / "frontend" / "src"
DOC_ROOT = ROOT / "docs"
README = ROOT / "README.md"
PADDLEGAN_WEIGHTS = ROOT / "backend" / "app" / "algorithms" / "paddle" / "paddlegan_vsr" / "weights.py"
STAGE_WORKER = ROOT / "backend" / "app" / "processing" / "streaming" / "stage_worker.py"
WORKER_PIPELINE = ROOT / "backend" / "app" / "processing" / "streaming" / "worker_pipeline.py"
CLI_DEFAULTS = ROOT / "backend" / "app" / "cli" / "defaults.py"
ENHANCE_FORM = FRONTEND_SRC / "composables" / "forms" / "useEnhanceForm.ts"
FRONTEND_FORM_COMPOSABLES = [
    FRONTEND_SRC / "composables" / "forms" / "useDecodeForm.ts",
    FRONTEND_SRC / "composables" / "forms" / "useEncodeForm.ts",
]


def _read(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_source_files(*roots: Path) -> list[Path]:
    suffixes = {".ts", ".tsx", ".vue"}
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                files.append(path)
    return files


def _is_test_file(path: Path) -> bool:
    parts = set(path.parts)
    return path.name.endswith(".spec.ts") or "__tests__" in parts or "e2e" in parts


def _allow_token(command: str) -> str:
    return f"allow-{command.replace('_', '-')}"


def _snake_to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _find_matching(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    raise RuntimeError(f"could not find matching {close_char!r}")


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    pairs = {"<": ">", "(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    for index, char in enumerate(text):
        if char in pairs:
            depth += 1
        elif char in closers:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _is_tauri_injected_param(type_name: str) -> bool:
    type_name = type_name.strip()
    return (
        type_name.startswith("AppHandle")
        or type_name.startswith("State<")
        or type_name.startswith("tauri::AppHandle")
        or type_name.startswith("tauri::State<")
    )


def _collect_manifest_commands() -> set[str]:
    text = _read(COMMANDS_MANIFEST)
    match = re.search(r"APP_COMMAND_NAMES:\s*&\[&str\]\s*=\s*&\[(?P<body>.*?)\];", text, re.DOTALL)
    if not match:
        raise RuntimeError("could not parse APP_COMMAND_NAMES in commands_manifest.rs")
    return set(re.findall(r'"([a-z_]+)"', match.group("body")))


def _collect_permission_commands() -> set[str]:
    text = _read(DEFAULT_PERMISSIONS)
    tokens = set(re.findall(r'"(allow-[a-z-]+)"', text))
    return {token.removeprefix("allow-").replace("-", "_") for token in tokens}


def _collect_frontend_invoke_commands() -> set[str]:
    commands: set[str] = set()
    pattern = re.compile(r"safeInvoke(?:<[^>]+>)?\(\s*['\"]([a-z_]+)['\"]")
    for path in _iter_source_files(IPC_ENDPOINT_DIR):
        commands.update(pattern.findall(_read(path)))
    return commands


def _collect_typed_ipc_contract_commands() -> set[str]:
    text = _read(IPC_CONTRACT)
    match = re.search(r"IPC_COMMAND_NAMES\s*=\s*\[(?P<body>.*?)\]\s*as\s+const", text, re.DOTALL)
    if not match:
        raise RuntimeError("could not parse IPC_COMMAND_NAMES in frontend IPC contract")
    return set(re.findall(r"['\"]([a-z_]+)['\"]", match.group("body")))


def _collect_rust_command_args() -> dict[str, set[str]]:
    command_args: dict[str, set[str]] = {}
    command_attr = re.compile(r"^\s*#\s*\[\s*tauri::command\s*\]", re.MULTILINE)
    function_decl = re.compile(r"(?:#\[[^\]]+\]\s*)*pub\s+(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)")

    for path in sorted(TAURI_SRC.rglob("*.rs")):
        text = _read(path)
        for attr_match in command_attr.finditer(text):
            fn_match = function_decl.search(text, attr_match.end())
            if not fn_match:
                raise RuntimeError(f"could not parse tauri command function after attr in {_rel(path)}")
            command = fn_match.group(1)
            args_start = text.find("(", fn_match.end())
            if args_start < 0:
                raise RuntimeError(f"could not parse args for tauri command `{command}` in {_rel(path)}")
            args_end = _find_matching(text, args_start, "(", ")")
            args = set()
            for param in _split_top_level_commas(text[args_start + 1 : args_end]):
                if ":" not in param:
                    continue
                raw_name, raw_type = param.split(":", 1)
                name = raw_name.strip().removeprefix("mut ").strip()
                type_name = raw_type.strip()
                if _is_tauri_injected_param(type_name):
                    continue
                args.add(_snake_to_camel(name) if "_" in name else name)
            command_args[command] = args

    return command_args


def _collect_typed_ipc_contract_args() -> dict[str, set[str]]:
    text = _read(IPC_CONTRACT)
    match = re.search(r"export\s+interface\s+IpcCommandArgs\s*\{", text)
    if not match:
        raise RuntimeError("could not parse IpcCommandArgs in frontend IPC contract")
    body_start = text.find("{", match.start())
    body_end = _find_matching(text, body_start, "{", "}")
    body = text[body_start + 1 : body_end]
    command_args: dict[str, set[str]] = {}

    for line in body.splitlines():
        line = line.strip().rstrip(",;")
        if not line:
            continue
        match = re.match(r"([a-z_]+):\s*(.+)$", line)
        if not match:
            raise RuntimeError(f"could not parse IpcCommandArgs line: {line}")
        command, value = match.groups()
        value = value.strip()
        if value == "undefined":
            command_args[command] = set()
            continue
        if value.startswith("{") and value.endswith("}"):
            command_args[command] = set(re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*:", value))
            continue
        raise RuntimeError(f"unsupported IpcCommandArgs shape for `{command}`: {value}")

    return command_args


def _check_command_surface(issues: list[str]) -> None:
    manifest = _collect_manifest_commands()
    permissions = _collect_permission_commands()
    invokes = _collect_frontend_invoke_commands()
    contract = _collect_typed_ipc_contract_commands()
    rust_args = _collect_rust_command_args()
    rust_commands = set(rust_args)
    contract_args = _collect_typed_ipc_contract_args()

    expected_permissions = {_allow_token(command) for command in manifest}
    raw_permission_tokens = set(re.findall(r'"(allow-[a-z-]+)"', _read(DEFAULT_PERMISSIONS)))
    if raw_permission_tokens != expected_permissions:
        issues.append(
            "Tauri permission command tokens drift: "
            f"missing={sorted(expected_permissions - raw_permission_tokens)}, "
            f"extra={sorted(raw_permission_tokens - expected_permissions)}"
        )

    if permissions != manifest:
        issues.append(
            "commands_manifest.rs and permissions/default.toml drift: "
            f"only-in-manifest={sorted(manifest - permissions)}, "
            f"only-in-permissions={sorted(permissions - manifest)}"
        )

    if rust_commands != manifest:
        issues.append(
            "tauri command functions drift from command manifest: "
            f"only-in-manifest={sorted(manifest - rust_commands)}, only-in-rust={sorted(rust_commands - manifest)}"
        )

    if invokes != manifest:
        issues.append(
            "frontend IPC endpoint safeInvoke commands drift from command manifest: "
            f"only-in-manifest={sorted(manifest - invokes)}, only-in-frontend={sorted(invokes - manifest)}"
        )

    if contract != manifest:
        issues.append(
            "frontend typed IPC contract commands drift from command manifest: "
            f"only-in-manifest={sorted(manifest - contract)}, only-in-contract={sorted(contract - manifest)}"
        )

    for command in sorted(manifest & set(rust_args) & set(contract_args)):
        if rust_args[command] != contract_args[command]:
            issues.append(
                f"IPC command args drift for `{command}`: "
                f"rust={sorted(rust_args[command])}, contract={sorted(contract_args[command])}"
            )


def _check_docs_do_not_reference_legacy_commands(issues: list[str]) -> None:
    legacy = ("pause_task", "resume_task")
    doc_files = [README, *sorted(DOC_ROOT.rglob("*.md"))]
    for path in doc_files:
        text = _read(path)
        for token in legacy:
            if token in text:
                issues.append(f"legacy command `{token}` remains in docs file {_rel(path)}")


def _check_generated_type_import_boundary(issues: list[str]) -> None:
    allowed_dir = FRONTEND_SRC / "types" / "protocol"
    generated_dir = FRONTEND_SRC / "types" / "generated"
    for path in _iter_source_files(FRONTEND_SRC):
        if _is_test_file(path):
            continue
        if allowed_dir in path.parents or generated_dir in path.parents:
            continue
        if "@/types/generated/" in _read(path):
            issues.append(f"generated type deep import outside protocol layer: {_rel(path)}")


def _check_ui_and_store_ipc_boundary(issues: list[str]) -> None:
    restricted_roots = [
        FRONTEND_SRC / "views",
        FRONTEND_SRC / "components",
        FRONTEND_SRC / "stores",
    ]
    markers = ("@/lib/ipc", "@tauri-apps/api", "safeInvoke(")
    for path in _iter_source_files(*restricted_roots):
        if _is_test_file(path):
            continue
        text = _read(path)
        if any(marker in text for marker in markers):
            issues.append(f"direct IPC access in UI/store layer: {_rel(path)}")


def _collect_python_dict_keys(text: str, symbol: str) -> set[str]:
    assignment = text.find(symbol)
    if assignment < 0:
        raise RuntimeError(f"could not find `{symbol}`")
    body_start = text.find("{", assignment)
    if body_start < 0:
        raise RuntimeError(f"could not find dict body for `{symbol}`")
    body_end = _find_matching(text, body_start, "{", "}")
    body = text[body_start + 1 : body_end]
    return set(re.findall(r"['\"]([a-z0-9-]+)['\"]\s*:", body))


def _collect_backend_paddlegan_enabled_models() -> set[str]:
    return _collect_python_dict_keys(_read(PADDLEGAN_WEIGHTS), "PADDLEGAN_VSR_SPECS")


def _collect_backend_paddlegan_disabled_models() -> set[str]:
    return _collect_python_dict_keys(_read(PADDLEGAN_WEIGHTS), "DISABLED_PADDLEGAN_VSR_MODELS")


def _collect_backend_algorithm_metadata() -> dict[str, dict[str, object]]:
    backend_dir = ROOT / "backend"
    inserted = False
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
        inserted = True
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from app.processing.super_resolution import SUPPORTED_ALGORITHMS

        return {
            str(entry["name"]): {
                "family": entry.get("family"),
                "fixedScaleFactor": entry.get("fixedScaleFactor"),
                "inputFrameMode": entry.get("inputFrameMode"),
            }
            for entry in SUPPORTED_ALGORITHMS
        }
    finally:
        if inserted:
            try:
                sys.path.remove(str(backend_dir))
            except ValueError:
                pass


def _diff_paddlegan_vsr_contract(
    backend_specs: set[str],
    backend_disabled: set[str],
    algorithm_metadata: dict[str, dict[str, object]],
) -> list[str]:
    issues: list[str] = []

    metadata_models = {
        name for name, metadata in algorithm_metadata.items() if metadata.get("family") == "paddlegan_vsr"
    }
    missing_metadata = backend_specs - metadata_models
    extra_metadata = metadata_models - backend_specs
    if missing_metadata or extra_metadata:
        issues.append(
            "PaddleGAN VSR backend specs and algorithm metadata drift: "
            f"missing-metadata={sorted(missing_metadata)}, extra-metadata={sorted(extra_metadata)}"
        )

    enabled_disabled_overlap = backend_specs & backend_disabled
    if enabled_disabled_overlap:
        issues.append(f"PaddleGAN VSR models cannot be both enabled and disabled: {sorted(enabled_disabled_overlap)}")

    metadata_disabled_overlap = metadata_models & backend_disabled
    if metadata_disabled_overlap:
        issues.append(
            f"Algorithm metadata re-exposes disabled PaddleGAN VSR models: {sorted(metadata_disabled_overlap)}"
        )

    for model_id in sorted(backend_specs & metadata_models):
        metadata = algorithm_metadata[model_id]
        if metadata.get("fixedScaleFactor") != 4:
            issues.append(
                f"PaddleGAN VSR metadata for `{model_id}` must expose fixedScaleFactor=4; "
                f"got {metadata.get('fixedScaleFactor')!r}"
            )
        expected_frame_mode = "fixed_window" if model_id == "edvr" else "editable_chunk"
        if metadata.get("inputFrameMode") != expected_frame_mode:
            issues.append(
                f"PaddleGAN VSR metadata for `{model_id}` must expose inputFrameMode={expected_frame_mode!r}; "
                f"got {metadata.get('inputFrameMode')!r}"
            )
    return issues


def _check_paddlegan_vsr_contract(issues: list[str]) -> None:
    issues.extend(
        _diff_paddlegan_vsr_contract(
            _collect_backend_paddlegan_enabled_models(),
            _collect_backend_paddlegan_disabled_models(),
            _collect_backend_algorithm_metadata(),
        )
    )


def _check_stage_worker_private_import_boundary(issues: list[str]) -> None:
    text = _read(STAGE_WORKER)
    if re.search(r"from\s+app\.processing\.streaming\.processor\s+import\s+[^\n]*_", text):
        issues.append("stage_worker.py imports processor private helpers instead of shared stage runtime helpers")


def _check_frontend_form_profile_rule_boundary(issues: list[str]) -> None:
    forbidden_tokens = (
        "seedProfileOptions",
        "resolveRateControlForProfile",
        "profile.family ===",
    )
    for path in FRONTEND_FORM_COMPOSABLES:
        text = _read(path)
        for token in forbidden_tokens:
            if token in text:
                issues.append(f"profile rule `{token}` leaked into form composable: {_rel(path)}")


def _check_cli_defaults_planning_boundary(issues: list[str]) -> None:
    text = _read(CLI_DEFAULTS)
    forbidden_patterns = {
        "PROCESS_ORDER_MAP": r"\bPROCESS_ORDER_MAP\b",
        "PROCESS_LABEL_MAP": r"\bPROCESS_LABEL_MAP\b",
        "resolve_primary_algorithm": r"def\s+_?resolve_primary_algorithm\b",
        "resolve_processing_steps": r"def\s+_?resolve_processing_steps\b",
        "processing_needs_interpolation": r"def\s+_?processing_needs_interpolation\b",
        "resolve_workflow_and_output_fps": r"def\s+_?resolve_workflow_and_output_fps\b",
        "resolve_expected_output_frames": r"def\s+_?resolve_expected_output_frames\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(f"workflow planning rule `{label}` remains in backend/app/cli/defaults.py")


def _check_frontend_enhance_workflow_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_FORM)
    forbidden_tokens = (
        "pickDefaultInterpolationAlgorithm",
        "pickDefaultInterpolationModel",
        "pickDefaultSuperResolutionAlgorithm",
        "pickDefaultEngine",
        "fallbackInterpolationOnnxModel",
        "fallbackSuperResolutionOnnxModel",
        "applySuperResolutionAlgorithmDefaults",
        "fixedSuperResolutionScaleFactor",
    )
    for token in forbidden_tokens:
        if token in text:
            issues.append(f"enhance workflow rule `{token}` leaked into form composable: {_rel(ENHANCE_FORM)}")


def _check_frontend_enhance_view_model_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_FORM)
    forbidden_patterns = {
        "model-metrics import": r"from\s+['\"]@/services/model-metrics['\"]",
        "enhance-rules import": r"from\s+['\"]@/services/preset/enhance-rules['\"]",
        "estimateModelRuntimeMetrics": r"\bestimateModelRuntimeMetrics\s*\(",
        "estimateCombinedPeakVram": r"\bestimateCombinedPeakVram\s*\(",
        "combinedVramMetricRows": r"\bcombinedVramMetricRows\s*\(",
        "metricRows": r"\bmetricRows\s*\(",
        "resolveMetricsForEngine": r"\bresolveMetricsForEngine\s*\(",
        "fixedRuntimeFrameCount": r"\bfixedRuntimeFrameCount\s*\(",
        "isPaddleGanVsrAlgorithm": r"\bisPaddleGanVsrAlgorithm\s*\(",
        "superResolutionInputFrameMode": r"\bsuperResolutionInputFrameMode\s*\(",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(f"enhance view-model rule `{label}` leaked into form composable: {_rel(ENHANCE_FORM)}")


def _check_worker_pipeline_plan_boundary(issues: list[str]) -> None:
    text = _read(WORKER_PIPELINE)
    forbidden_patterns = {
        "StageWorkerPlan": r"^\s*class\s+StageWorkerPlan\b",
        "StageChunkPlan": r"^\s*class\s+StageChunkPlan\b",
        "build_stage_worker_plans": r"^\s*def\s+build_stage_worker_plans\b",
        "build_stage_chunk_plans": r"^\s*def\s+build_stage_chunk_plans\b",
        "boundary_schedule_for_stage_plan": r"^\s*def\s+boundary_schedule_for_stage_plan\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"worker plan rule `{label}` remains in backend/app/processing/streaming/worker_pipeline.py")


def _check_worker_pipeline_process_boundary(issues: list[str]) -> None:
    text = _read(WORKER_PIPELINE)
    forbidden_patterns = {
        "_WorkerHandle": r"^\s*class\s+_WorkerHandle\b",
        "parse_stage_event_line": r"^\s*def\s+parse_stage_event_line\b",
        "_spawn_stage_workers": r"^\s*def\s+_spawn_stage_workers\b",
        "_read_worker_stderr": r"^\s*def\s+_read_worker_stderr\b",
        "_write_decoded_frames_to_worker": r"^\s*def\s+_write_decoded_frames_to_worker\b",
        "_drain_final_worker_output": r"^\s*def\s+_drain_final_worker_output\b",
        "_wait_for_workers": r"^\s*def\s+_wait_for_workers\b",
        "_close_pipe": r"^\s*def\s+_close_pipe\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"worker process helper `{label}` remains in backend/app/processing/streaming/worker_pipeline.py"
            )


def main() -> int:
    issues: list[str] = []
    try:
        _check_command_surface(issues)
        _check_docs_do_not_reference_legacy_commands(issues)
        _check_generated_type_import_boundary(issues)
        _check_ui_and_store_ipc_boundary(issues)
        _check_paddlegan_vsr_contract(issues)
        _check_stage_worker_private_import_boundary(issues)
        _check_frontend_form_profile_rule_boundary(issues)
        _check_cli_defaults_planning_boundary(issues)
        _check_frontend_enhance_workflow_boundary(issues)
        _check_frontend_enhance_view_model_boundary(issues)
        _check_worker_pipeline_plan_boundary(issues)
        _check_worker_pipeline_process_boundary(issues)
    except RuntimeError as exc:
        sys.stderr.write(f"[check-architecture-contracts] PARSE ERROR: {exc}\n")
        return 2

    if issues:
        sys.stderr.write("[check-architecture-contracts] DRIFT DETECTED:\n")
        for issue in issues:
            sys.stderr.write(f"  - {issue}\n")
        return 1

    sys.stdout.write("[check-architecture-contracts] OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
