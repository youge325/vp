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
STAGE_WORKER_RUNTIME = ROOT / "backend" / "app" / "processing" / "streaming" / "stage_worker_runtime.py"
STAGE_FILE_CHUNK_ENCODING = ROOT / "backend" / "app" / "processing" / "streaming" / "stage_file_chunk_encoding.py"
WORKER_PIPELINE = ROOT / "backend" / "app" / "processing" / "streaming" / "worker_pipeline.py"
WORKER_CHAIN_RUNTIME = ROOT / "backend" / "app" / "processing" / "streaming" / "worker_chain_runtime.py"
WORKER_PROCESSES = ROOT / "backend" / "app" / "processing" / "streaming" / "worker_processes.py"
WORKER_PROCESS_EVENTS = ROOT / "backend" / "app" / "processing" / "streaming" / "worker_process_events.py"
WORKER_PROCESS_IO = ROOT / "backend" / "app" / "processing" / "streaming" / "worker_process_io.py"
ENCODER = ROOT / "backend" / "app" / "processing" / "streaming" / "encoder.py"
ENCODER_WORKER = ROOT / "backend" / "app" / "processing" / "streaming" / "encoder_worker.py"
PIPELINE_RAW = ROOT / "backend" / "app" / "processing" / "streaming" / "pipeline_raw.py"
PIPELINE_RAW_RUNTIME = ROOT / "backend" / "app" / "processing" / "streaming" / "pipeline_raw_runtime.py"
STREAMING_PIPELINE = ROOT / "backend" / "app" / "processing" / "streaming" / "pipeline.py"
PIPELINE_LIFECYCLE = ROOT / "backend" / "app" / "processing" / "streaming" / "pipeline_lifecycle.py"
STAGE_FILE_PIPELINE = ROOT / "backend" / "app" / "processing" / "streaming" / "stage_file_pipeline.py"
STAGE_FILE_CHUNK_RUNTIME = ROOT / "backend" / "app" / "processing" / "streaming" / "stage_file_chunk_runtime.py"
STAGE_FILE_CHUNKS = ROOT / "backend" / "app" / "processing" / "streaming" / "stage_file_chunks.py"
PROCESSOR = ROOT / "backend" / "app" / "processing" / "streaming" / "processor.py"
PROCESSOR_STREAMS = ROOT / "backend" / "app" / "processing" / "streaming" / "processor_streams.py"
CLI_DEFAULTS = ROOT / "backend" / "app" / "cli" / "defaults.py"
MODEL_METRICS = FRONTEND_SRC / "services" / "model-metrics.ts"
PRESET_DEFAULTS = FRONTEND_SRC / "services" / "preset" / "defaults.ts"
ENHANCE_RULES = FRONTEND_SRC / "services" / "preset" / "enhance-rules.ts"
ENHANCE_DEFAULT_SELECTION = FRONTEND_SRC / "services" / "preset" / "enhance-default-selection.ts"
ENHANCE_WORKFLOW = FRONTEND_SRC / "services" / "preset" / "enhance-workflow.ts"
ENHANCE_WORKFLOW_SELECTION = FRONTEND_SRC / "services" / "preset" / "enhance-workflow-selection.ts"
ENHANCE_VIEW_MODEL = FRONTEND_SRC / "services" / "preset" / "enhance-view-model.ts"
ENHANCE_RUNTIME_VIEW = FRONTEND_SRC / "services" / "preset" / "enhance-runtime-view.ts"
ENHANCE_FORM = FRONTEND_SRC / "composables" / "forms" / "useEnhanceForm.ts"
ENHANCE_FORM_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "enhance-form-bindings.ts"
ENHANCE_FIELD_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "enhance-field-bindings.ts"
ENHANCE_OPTION_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "enhance-option-bindings.ts"
DECODE_FORM_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "decode-form-bindings.ts"
ENCODE_FORM_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "encode-form-bindings.ts"
DECODE_PROFILE_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "decode-profile-bindings.ts"
ENCODE_PROFILE_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "encode-profile-bindings.ts"
ENCODE_OUTPUT_BINDINGS = FRONTEND_SRC / "composables" / "forms" / "encode-output-bindings.ts"
ENHANCE_VIEW = FRONTEND_SRC / "views" / "EnhanceModuleView.vue"
DECODE_VIEW = FRONTEND_SRC / "views" / "DecodeModuleView.vue"
ENCODE_VIEW = FRONTEND_SRC / "views" / "EncodeModuleView.vue"
FRONTEND_FORM_COMPOSABLES = [
    FRONTEND_SRC / "composables" / "forms" / "useDecodeForm.ts",
    FRONTEND_SRC / "composables" / "forms" / "useEncodeForm.ts",
]
FRONTEND_IO_FORM_BINDINGS = [
    DECODE_FORM_BINDINGS,
    ENCODE_FORM_BINDINGS,
]
FRONTEND_IO_PROFILE_BINDINGS = [
    DECODE_PROFILE_BINDINGS,
    ENCODE_PROFILE_BINDINGS,
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


def _check_stage_worker_runtime_boundary(issues: list[str]) -> None:
    text = _read(STAGE_WORKER)
    forbidden_patterns = {
        "RawVideoFrameError": r"^\s*class\s+RawVideoFrameError\b",
        "read_rgb_frame": r"^\s*def\s+read_rgb_frame\b",
        "write_rgb_frame": r"^\s*def\s+write_rgb_frame\b",
        "emit_stage_event": r"^\s*def\s+emit_stage_event\b",
        "_create_backend": r"^\s*def\s+_create_backend\b",
        "_create_algorithm": r"^\s*def\s+_create_algorithm\b",
        "_register_single_algorithm": r"^\s*def\s+_register_single_algorithm\b",
        "_backend_name": r"^\s*def\s+_backend_name\b",
        "_read_declared_frames": r"^\s*def\s+_read_declared_frames\b",
        "_progress_event": r"^\s*def\s+_progress_event\b",
        "_StageProgressState": r"^\s*class\s+_StageProgressState\b",
        "_start_sequence_stage_heartbeat": r"^\s*def\s+_start_sequence_stage_heartbeat\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"stage worker runtime rule `{label}` remains in backend/app/processing/streaming/stage_worker.py"
            )


def _check_stage_worker_helper_import_boundary(issues: list[str]) -> None:
    helper_tokens = (
        "RawVideoFrameError",
        "STAGE_EVENT_PREFIX",
        "emit_stage_event",
        "read_rgb_frame",
        "write_rgb_frame",
    )
    for path in (STAGE_FILE_CHUNK_ENCODING, WORKER_PROCESS_EVENTS, WORKER_PROCESS_IO):
        text = _read(path)
        for match in re.finditer(r"from\s+app\.processing\.streaming\.stage_worker\s+import\s+([^\n]+)", text):
            leaked = [token for token in helper_tokens if token in match.group(1)]
            for token in leaked:
                issues.append(f"stage worker helper `{token}` import remains in {_rel(path)}")


def _check_stage_worker_runtime_split_boundary(issues: list[str]) -> None:
    if not STAGE_WORKER_RUNTIME.exists():
        return

    text = _read(STAGE_WORKER_RUNTIME)
    if "Compatibility barrel" in text:
        issues.append(f"obsolete stage worker runtime barrel remains in {_rel(STAGE_WORKER_RUNTIME)}")
    forbidden_patterns = {
        "dataclass import": r"^\s*from\s+dataclasses\s+import\s+dataclass\b",
        "json import": r"^\s*import\s+json\b",
        "sys import": r"^\s*import\s+sys\b",
        "threading import": r"^\s*import\s+threading\b",
        "algorithm factory import": r"^\s*from\s+app\.algorithms\.factory\s+import\s+AlgorithmFactory\b",
        "stage kwargs import": r"\balgorithm_kwargs_for_create\b",
        "progress state": r"^\s*class\s+StageProgressState\b",
        "event emitter": r"^\s*def\s+emit_stage_event\b",
        "backend factory": r"^\s*def\s+create_backend\b",
        "algorithm factory": r"^\s*def\s+create_algorithm\b",
        "algorithm registration": r"^\s*def\s+register_single_algorithm\b",
        "backend name": r"^\s*def\s+backend_name\b",
        "progress event": r"^\s*def\s+progress_event\b",
        "sequence heartbeat": r"^\s*def\s+start_sequence_stage_heartbeat\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"stage worker runtime split `{label}` remains in {_rel(STAGE_WORKER_RUNTIME)}")


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


def _check_frontend_enhance_workflow_selection_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_WORKFLOW)
    forbidden_patterns = {
        "tensor backend list": r"\bTENSOR_BACKENDS\b",
        "interpolation algorithm finder": r"^\s*function\s+findInterpolationAlgorithm\b",
        "super-resolution algorithm finder": r"^\s*function\s+findSuperResolutionAlgorithm\b",
        "supported backend picker": r"^\s*function\s+pickSupportedBackend\b",
        "paddle sr onnx preference": r"^\s*function\s+preferOnnxInterpolationForPaddleSuperResolution\b",
        "interpolation onnx fallback": r"\bfallbackInterpolationOnnxModel\b",
        "super-resolution onnx fallback": r"\bfallbackSuperResolutionOnnxModel\b",
        "fixed runtime frames": r"\bfixedRuntimeFrameCount\b",
        "fixed scale factor": r"\bfixedSuperResolutionScaleFactor\b",
        "default engine picker": r"\bpickDefaultEngine\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"enhance workflow selection `{label}` remains in frontend/src/services/preset/enhance-workflow.ts"
            )


def _check_frontend_enhance_workflow_lookup_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_WORKFLOW_SELECTION)
    forbidden_patterns = {
        "tensor backend list": r"\bTENSOR_BACKENDS\b",
        "tensor backend guard": r"^\s*function\s+isTensorBackend\b",
        "interpolation algorithm finder": r"^\s*export\s+function\s+findInterpolationAlgorithm\b",
        "super-resolution algorithm finder": r"^\s*export\s+function\s+findSuperResolutionAlgorithm\b",
        "supported backend picker": r"^\s*export\s+function\s+pickSupportedBackend\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"enhance workflow lookup `{label}` remains in {_rel(ENHANCE_WORKFLOW_SELECTION)}")


def _check_frontend_enhance_rules_split_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_RULES)
    forbidden_patterns = {
        "nested default-selection barrel": r"export\s+\*\s+from\s+['\"]\.\/enhance-default-selection['\"]",
        "backend compatibility helper": r"^\s*function\s+backendCompatible\b",
        "PaddleGAN classifier": r"^\s*export\s+function\s+isPaddleGanVsrAlgorithm\b",
        "input frame mode": r"^\s*export\s+function\s+superResolutionInputFrameMode\b",
        "fixed runtime frames": r"^\s*export\s+function\s+fixedRuntimeFrameCount\b",
        "fixed scale factor": r"^\s*export\s+function\s+fixedSuperResolutionScaleFactor\b",
        "super-resolution defaults": r"^\s*export\s+function\s+applySuperResolutionAlgorithmDefaults\b",
        "default engine picker": r"^\s*export\s+function\s+pickDefaultEngine\b",
        "interpolation ONNX fallback": r"^\s*export\s+function\s+fallbackInterpolationOnnxModel\b",
        "super-resolution ONNX fallback": r"^\s*export\s+function\s+fallbackSuperResolutionOnnxModel\b",
        "default interpolation algorithm": r"^\s*export\s+function\s+pickDefaultInterpolationAlgorithm\b",
        "default interpolation model": r"^\s*export\s+function\s+pickDefaultInterpolationModel\b",
        "default super-resolution algorithm": r"^\s*export\s+function\s+pickDefaultSuperResolutionAlgorithm\b",
        "default anime profile": r"^\s*export\s+function\s+pickDefaultAnimeProfile\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"enhance rules split `{label}` remains in frontend/src/services/preset/enhance-rules.ts")


def _check_frontend_enhance_default_selection_split_boundary(issues: list[str]) -> None:
    if not ENHANCE_DEFAULT_SELECTION.exists():
        return
    text = _read(ENHANCE_DEFAULT_SELECTION)
    if re.search(r"^\s*export\s+\*\s+from\s+['\"]\./enhance-default-pickers['\"]", text, re.MULTILINE) or re.search(
        r"^\s*export\s+\*\s+from\s+['\"]\./enhance-onnx-defaults['\"]",
        text,
        re.MULTILINE,
    ):
        issues.append(f"obsolete enhance default-selection barrel remains in {_rel(ENHANCE_DEFAULT_SELECTION)}")
    forbidden_patterns = {
        "backend compatibility helper": r"^\s*function\s+backendCompatible\b",
        "default engine picker": r"^\s*export\s+function\s+pickDefaultEngine\b",
        "interpolation ONNX fallback": r"^\s*export\s+function\s+fallbackInterpolationOnnxModel\b",
        "super-resolution ONNX fallback": r"^\s*export\s+function\s+fallbackSuperResolutionOnnxModel\b",
        "default interpolation algorithm": r"^\s*export\s+function\s+pickDefaultInterpolationAlgorithm\b",
        "default interpolation model": r"^\s*export\s+function\s+pickDefaultInterpolationModel\b",
        "default super-resolution algorithm": r"^\s*export\s+function\s+pickDefaultSuperResolutionAlgorithm\b",
        "default anime profile": r"^\s*export\s+function\s+pickDefaultAnimeProfile\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"enhance default-selection split `{label}` remains in {_rel(ENHANCE_DEFAULT_SELECTION)}")


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


def _check_frontend_enhance_view_model_split_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_VIEW_MODEL)
    forbidden_patterns = {
        "model-metrics import": r"from\s+['\"]@/services/model-metrics['\"]",
        "algorithm capability import": r"from\s+['\"]\.\/enhance-algorithm-capabilities['\"]",
        "selected model detail": r"\bselectedModelDetail\b",
        "scaled dimensions": r"\bscaledDimensions\b",
        "metrics resolver": r"\bresolveMetricsForEngine\b",
        "runtime estimate": r"\bestimateModelRuntimeMetrics\b",
        "metric rows": r"\bmetricRows\b",
        "combined vram rows": r"\bcombinedVramMetricRows\s*\(",
        "combined peak vram": r"\bestimateCombinedPeakVram\b",
        "fixed frame helper": r"\bfixedRuntimeFrameCount\b",
        "PaddleGAN helper": r"\bisPaddleGanVsrAlgorithm\b",
        "input frame mode helper": r"\bsuperResolutionInputFrameMode\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"enhance view-model split `{label}` remains in {_rel(ENHANCE_VIEW_MODEL)}")


def _check_frontend_enhance_runtime_view_split_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_RUNTIME_VIEW)
    forbidden_patterns = {
        "model-metrics import": r"from\s+['\"]@/services/model-metrics['\"]",
        "algorithm capability import": r"from\s+['\"]\.\/enhance-algorithm-capabilities['\"]",
        "scaled dimensions": r"\bscaledDimensions\b",
        "runtime estimate": r"\bestimateModelRuntimeMetrics\b",
        "metric rows": r"\bmetricRows\s*\(",
        "combined vram rows": r"\bcombinedVramMetricRows\s*\(",
        "combined peak vram": r"\bestimateCombinedPeakVram\b",
        "fixed frame helper": r"\bfixedRuntimeFrameCount\b",
        "PaddleGAN helper": r"\bisPaddleGanVsrAlgorithm\b",
        "input frame mode helper": r"\bsuperResolutionInputFrameMode\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"enhance runtime-view split `{label}` remains in {_rel(ENHANCE_RUNTIME_VIEW)}")


def _check_frontend_model_metrics_barrel_boundary(issues: list[str]) -> None:
    text = _read(MODEL_METRICS)
    forbidden_patterns = {
        "format function": r"^\s*export\s+function\s+format(?:Bytes|Gflops|ParameterCount)\b",
        "model option label": r"^\s*export\s+function\s+modelOptionLabel\b",
        "engine resolver": r"^\s*export\s+function\s+resolveMetricsForEngine\b",
        "runtime estimate": r"^\s*export\s+function\s+estimateModelRuntimeMetrics\b",
        "combined vram estimate": r"^\s*export\s+function\s+estimateCombinedPeakVram\b",
        "metric rows": r"^\s*export\s+function\s+(?:metricRows|combinedVramMetricRows)\b",
        "local finite helper": r"^\s*function\s+finiteOrNull\b",
        "local padding helper": r"^\s*function\s+padToModulo\b",
        "local unknown sentinel": r"^\s*const\s+UNKNOWN\b",
        "runtime interface": r"^\s*export\s+interface\s+(?:VideoDimensions|RuntimeMetricOptions|RuntimeMetricEstimate)\b",
        "metric row interface": r"^\s*export\s+interface\s+MetricRow\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"model metrics barrel `{label}` remains in {_rel(MODEL_METRICS)}")


def _check_frontend_enhance_binding_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_FORM)
    forbidden_patterns = {
        "createDraftEditor": r"\bcreateDraftEditor\b",
        "createAlgorithmLens": r"\bcreateAlgorithmLens\b",
        "buildEnhanceViewModel": r"\bbuildEnhanceViewModel\b",
        "enhance workflow mutation import": r"\bapply(?:Interpolation|SuperResolution)[A-Za-z]+\b",
        "input frame label": r"\bsuperResolutionInputFramesLabel\b",
        "input frame hint": r"\bsuperResolutionInputFramesHint\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(f"enhance binding rule `{label}` leaked into form composable: {_rel(ENHANCE_FORM)}")


def _check_frontend_enhance_field_binding_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_FORM_BINDINGS)
    forbidden_patterns = {
        "createDraftEditor": r"\bcreateDraftEditor\b",
        "enhance workflow mutation import": r"from\s+['\"]@/services/preset/enhance-workflow['\"]",
        "workflow mutation function": r"\bapply(?:Interpolation|SuperResolution)[A-Za-z]+\b",
        "field writer": r"\bconst\s+[A-Za-z0-9]+\s*=\s*field\s*\(",
        "effect writer": r"\bconst\s+[A-Za-z0-9]+\s*=\s*effect\s*<",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(
                f"enhance field binding rule `{label}` leaked into form binding assembly: {_rel(ENHANCE_FORM_BINDINGS)}"
            )


def _check_frontend_enhance_field_split_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_FIELD_BINDINGS)
    forbidden_patterns = {
        "createDraftEditor": r"\bcreateDraftEditor\b",
        "enhance workflow mutation import": r"from\s+['\"]@/services/preset/enhance-workflow['\"]",
        "workflow mutation function": r"\bapply(?:Interpolation|SuperResolution)[A-Za-z]+\b",
        "field writer": r"\bconst\s+[A-Za-z0-9]+\s*=\s*field\s*\(",
        "effect writer": r"\bconst\s+[A-Za-z0-9]+\s*=\s*effect\s*<",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(
                f"enhance field split rule `{label}` leaked into field binding aggregator: "
                f"{_rel(ENHANCE_FIELD_BINDINGS)}"
            )


def _check_frontend_enhance_projection_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_FORM_BINDINGS)
    forbidden_patterns = {
        "enhance lens import": r"from\s+['\"]@/composables/forms/enhance-lens['\"]",
        "enhance view-model import": r"from\s+['\"]@/services/preset/enhance-view-model['\"]",
        "createAlgorithmLens": r"\bcreateAlgorithmLens\b",
        "buildEnhanceViewModel": r"\bbuildEnhanceViewModel\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(
                f"enhance projection rule `{label}` leaked into form binding assembly: {_rel(ENHANCE_FORM_BINDINGS)}"
            )


def _check_frontend_enhance_option_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_VIEW)
    forbidden_patterns = {
        "enhance-options import": r"from\s+['\"]@/services/preset/enhance-options['\"]",
        "gpu capabilities import": r"from\s+['\"]@/composables/selectors/useGpuCapabilities['\"]",
        "modelOptionLabel import": r"from\s+['\"]@/services/model-metrics['\"]",
        "gpu-label import": r"from\s+['\"]@/config/gpu-labels['\"]",
        "FPS_MODE_OPTIONS": r"\bconst\s+FPS_MODE_OPTIONS\b",
        "MULTI_OPTIONS": r"\bconst\s+MULTI_OPTIONS\b",
        "PROCESS_ORDER_OPTIONS": r"\bconst\s+PROCESS_ORDER_OPTIONS\b",
        "enhance option builder": r"\bbuild(?:Backend|Engine|Algorithm|Model|OnnxModel|Profile)Options\s*\(",
        "enhance value converter": r"\bto(?:TensorBackend|InferenceEngine|FpsMode|ProcessOrder|NumberOption)\s*\(",
        "enhance option setter": r"^\s*function\s+set(?:Interpolation|SuperResolution|Fps|ProcessOrder)\b",
        "findDetail": r"\bfunction\s+findDetail\b",
        "TensorBackend cast": r"\bas\s+TensorBackend\b",
        "InferenceEngine cast": r"\bas\s+InferenceEngine\b",
        "FpsMode cast": r"\bas\s+FpsMode\b",
        "ProcessOrder cast": r"\bas\s+ProcessOrder\b",
        "Number select cast": r"\bNumber\s*\(",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(f"enhance option rule `{label}` leaked into view: {_rel(ENHANCE_VIEW)}")


def _check_frontend_enhance_option_binding_boundary(issues: list[str]) -> None:
    text = _read(ENHANCE_OPTION_BINDINGS)
    forbidden_patterns = {
        "useGpuCapabilities": r"\buseGpuCapabilities\b",
        "enhance-options import": r"from\s+['\"]@/services/preset/enhance-options['\"]",
        "option builder": r"\bbuild(?:Backend|Engine|Algorithm|Model|OnnxModel|Profile)Options\s*\(",
        "value converter": r"\bto(?:TensorBackend|InferenceEngine|FpsMode|ProcessOrder|NumberOption)\s*\(",
        "option setter": r"^\s*function\s+set(?:Interpolation|SuperResolution|Fps|ProcessOrder|Anime)\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"enhance option binding rule `{label}` leaked into option binding aggregator: "
                f"{_rel(ENHANCE_OPTION_BINDINGS)}"
            )


def _check_frontend_io_view_option_boundary(issues: list[str]) -> None:
    forbidden_patterns = {
        "io-options import": r"from\s+['\"]@/services/preset/io-options['\"]",
        "profile option map": r"\.map\(\s*\(?\s*profile\s*\)?\s*=>\s*\(\{\s*value:\s*profile\.name,\s*label:\s*profile\.label",
        "container constants import": r"from\s+['\"]@/config/constants['\"]",
        "container option map": r"\bCONTAINER_OPTIONS\.map\b",
        "RateControlMode cast": r"\bas\s+RateControlMode\b",
        "Number select cast": r"\bNumber\s*\(",
    }
    for path in (DECODE_VIEW, ENCODE_VIEW):
        text = _read(path)
        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, text, re.DOTALL):
                issues.append(f"io option rule `{label}` leaked into view: {_rel(path)}")


def _check_frontend_io_form_rule_boundary(issues: list[str]) -> None:
    forbidden_patterns = {
        "hardware device map": r"\bhardwareDevices\b.{0,120}\.map\s*\(",
        "decoder device options": r"\bgetDecoderHwaccelDeviceOptions\b",
        "decoder device resolve": r"\bresolveDecoderHwaccelDevice\b",
        "rate control mode options": r"\bgetRateControlModeOptions\b",
        "rate control modes check": r"\bhasRateControlModes\b",
        "rate control unit": r"\bgetRateControlUnit\b",
        "rate control mode resolve": r"\bresolveRateControlForMode\b",
        "segment frames normalize": r"\bNumber\.isFinite\b",
    }
    for path in FRONTEND_FORM_COMPOSABLES:
        text = _read(path)
        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, text, re.DOTALL):
                issues.append(f"io form rule `{label}` leaked into form composable: {_rel(path)}")


def _check_frontend_io_form_binding_boundary(issues: list[str]) -> None:
    forbidden_patterns = {
        "profile-picker import": r"from\s+['\"]@/services/preset/profile-picker['\"]",
        "profile-selection import": r"from\s+['\"]@/services/preset/profile-selection['\"]",
        "io-form-rules import": r"from\s+['\"]@/services/preset/io-form-rules['\"]",
        "preset options import": r"from\s+['\"]@/services/preset/options['\"]",
        "preset normalize import": r"from\s+['\"]@/services/preset/normalize['\"]",
    }
    for path in FRONTEND_FORM_COMPOSABLES:
        text = _read(path)
        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, text):
                issues.append(f"io form binding rule `{label}` leaked into form composable: {_rel(path)}")


def _check_frontend_io_form_aggregator_boundary(issues: list[str]) -> None:
    forbidden_patterns = {
        "profile-picker import": r"from\s+['\"]@/services/preset/profile-picker['\"]",
        "profile-selection import": r"from\s+['\"]@/services/preset/profile-selection['\"]",
        "io-form-rules import": r"from\s+['\"]@/services/preset/io-form-rules['\"]",
        "preset options import": r"from\s+['\"]@/services/preset/options['\"]",
        "preset normalize import": r"from\s+['\"]@/services/preset/normalize['\"]",
        "io-options import": r"from\s+['\"]@/services/preset/io-options['\"]",
    }
    for path in FRONTEND_IO_FORM_BINDINGS:
        text = _read(path)
        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, text):
                issues.append(f"io form rule `{label}` leaked into form binding aggregator: {_rel(path)}")


def _check_frontend_io_profile_state_boundary(issues: list[str]) -> None:
    forbidden_patterns = {
        "buildProfileOptions import": r"\bbuildProfileOptions\b",
        "current profile computed": r"\bcurrent(?:Decoder|Encoder)Profile\s*=\s*computed\s*\(",
        "capability options computed": r"\b(?:decoder|encoder)Options\s*=\s*computed\s*\(",
    }
    for path in FRONTEND_IO_PROFILE_BINDINGS:
        text = _read(path)
        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, text):
                issues.append(f"io profile state rule `{label}` leaked into profile binding: {_rel(path)}")


def _check_frontend_decode_hardware_binding_boundary(issues: list[str]) -> None:
    text = _read(DECODE_PROFILE_BINDINGS)
    forbidden_patterns = {
        "io-form-rules import": r"from\s+['\"]@/services/preset/io-form-rules['\"]",
        "hardware option builder": r"\bbuildDecoderHardwareDevice(?:Number)?Options\b",
        "hardware selection rule": r"\bapplyDecodeHwaccel(?:Device)?Selection\b",
        "hardware option computed": r"\bdecoderHardwareDevice(?:Number)?Options\s*=\s*computed\s*\(",
        "hardware setter": r"^\s*function\s+setDecodeHwaccel(?:Device)?\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"decode hardware binding rule `{label}` leaked into profile binding: {_rel(DECODE_PROFILE_BINDINGS)}"
            )


def _check_frontend_defaults_workflow_boundary(issues: list[str]) -> None:
    text = _read(PRESET_DEFAULTS)
    forbidden_patterns = {
        "enhance-rules import": r"from\s+['\"]\.\/enhance-rules['\"]",
        "workflow engine type import": r"\bInferenceEngine\b",
        "default interpolation picker": r"\bpickDefaultInterpolationAlgorithm\b",
        "default super-resolution picker": r"\bpickDefaultSuperResolutionAlgorithm\b",
        "super-resolution defaults": r"\bapplySuperResolutionAlgorithmDefaults\b",
        "anime default picker": r"\bpickDefaultAnimeProfile\b",
        "tensor engine lookup": r"\btensorEngines\b",
        "gpu vendor lookup": r"\bgpu\?\.adapters\b",
        "vendor branch": r"\bvendor\s*===\s*['\"](?:hygon|nvidia)['\"]",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(
                f"workflow default rule `{label}` leaked into preset defaults factory: {_rel(PRESET_DEFAULTS)}"
            )


def _check_frontend_encode_output_binding_boundary(issues: list[str]) -> None:
    text = _read(ENCODE_OUTPUT_BINDINGS)
    forbidden_patterns = {
        "io-options import": r"from\s+['\"]@/services/preset/io-options['\"]",
        "io-form-rules import": r"from\s+['\"]@/services/preset/io-form-rules['\"]",
        "preset normalize import": r"from\s+['\"]@/services/preset/normalize['\"]",
        "container options computed": r"\bcontainerOptions\s*=\s*computed\s*\(",
        "segment frames computed": r"\bsegmentFramesValue\s*=\s*computed\s*\(",
        "output setter": r"^\s*function\s+set(?:Container|KeepAudio|OutputDir|OpenOnComplete|SegmentFrames)\b",
        "output normalizer": r"\bnormalize(?:OutputDir|SegmentFrames)\b",
        "select value conversion": r"\b(?:CONTAINER_SELECT_OPTIONS|toNumberValue)\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"encode output binding rule `{label}` leaked into binding aggregator: {_rel(ENCODE_OUTPUT_BINDINGS)}"
            )


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


def _check_worker_pipeline_chain_runtime_boundary(issues: list[str]) -> None:
    text = _read(WORKER_PIPELINE)
    forbidden_patterns = {
        "Path import": r"^\s*from\s+pathlib\s+import\s+Path\b",
        "sys import": r"^\s*import\s+sys\b",
        "tempfile import": r"^\s*import\s+tempfile\b",
        "threading import": r"^\s*import\s+threading\b",
        "temporary directory": r"\bTemporaryDirectory\s*\(",
        "thread allocation": r"\bthreading\.Thread\s*\(",
        "close_pipe": r"\bclose_pipe\b",
        "drain_final_worker_output": r"\bdrain_final_worker_output\b",
        "read_worker_stderr": r"\bread_worker_stderr\b",
        "spawn_stage_workers": r"\bspawn_stage_workers\b",
        "wait_for_workers": r"\bwait_for_workers\b",
        "write_decoded_frames_to_worker": r"\bwrite_decoded_frames_to_worker\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"worker chain runtime `{label}` remains in backend/app/processing/streaming/worker_pipeline.py"
            )


def _check_worker_pipeline_file_boundary(issues: list[str]) -> None:
    text = _read(WORKER_PIPELINE)
    forbidden_patterns = {
        "run_stage_file_pipeline": r"^\s*def\s+run_stage_file_pipeline\b",
        "_run_single_stage_file_chunks": r"^\s*def\s+_run_single_stage_file_chunks\b",
        "_run_stage_chunk_to_file": r"^\s*def\s+_run_stage_chunk_to_file\b",
        "_chunk_progress_adapter": r"^\s*def\s+_chunk_progress_adapter\b",
        "_stage_chunk_output_start": r"^\s*def\s+_stage_chunk_output_start\b",
        "_stage_signature": r"^\s*def\s+_stage_signature\b",
        "_safe_stage_name": r"^\s*def\s+_safe_stage_name\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"stage file pipeline helper `{label}` remains in backend/app/processing/streaming/worker_pipeline.py"
            )


def _check_worker_processes_event_io_boundary(issues: list[str]) -> None:
    text = _read(WORKER_PROCESSES)
    forbidden_patterns = {
        "parse_stage_event_line": r"^\s*def\s+parse_stage_event_line\b",
        "read_worker_stderr": r"^\s*def\s+read_worker_stderr\b",
        "write_decoded_frames_to_worker": r"^\s*def\s+write_decoded_frames_to_worker\b",
        "drain_final_worker_output": r"^\s*def\s+drain_final_worker_output\b",
        "close_pipe": r"^\s*def\s+close_pipe\b",
        "TENSORRT_LOG_PREFIX": r"\bTENSORRT_LOG_PREFIX\b",
        "STAGE_EVENT_PREFIX": r"\bSTAGE_EVENT_PREFIX\b",
        "read_rgb_frame": r"\bread_rgb_frame\b",
        "write_rgb_frame": r"\bwrite_rgb_frame\b",
        "boundary_schedule_for_stage_plan": r"\bboundary_schedule_for_stage_plan\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"worker process event/io helper `{label}` remains in "
                "backend/app/processing/streaming/worker_processes.py"
            )


def _check_worker_process_helper_import_boundary(issues: list[str]) -> None:
    helper_tokens = (
        "close_pipe",
        "drain_final_worker_output",
        "parse_stage_event_line",
        "read_worker_stderr",
        "write_decoded_frames_to_worker",
    )
    import_pattern = re.compile(
        r"from\s+app\.processing\.streaming\.worker_processes\s+import\s+(?:\((?P<block>.*?)\)|(?P<line>[^\n]+))",
        re.DOTALL,
    )
    for path in (STAGE_FILE_CHUNK_RUNTIME, WORKER_CHAIN_RUNTIME, WORKER_PIPELINE):
        text = _read(path)
        for match in import_pattern.finditer(text):
            imported_names = match.group("block") or match.group("line") or ""
            leaked = [token for token in helper_tokens if token in imported_names]
            for token in leaked:
                issues.append(f"worker process helper `{token}` import remains in {_rel(path)}")


def _check_stage_file_pipeline_chunk_boundary(issues: list[str]) -> None:
    text = _read(STAGE_FILE_PIPELINE)
    forbidden_patterns = {
        "_run_single_stage_file_chunks": r"^\s*def\s+_run_single_stage_file_chunks\b",
        "_run_stage_chunk_to_file": r"^\s*def\s+_run_stage_chunk_to_file\b",
        "_chunk_progress_adapter": r"^\s*def\s+_chunk_progress_adapter\b",
        "_stage_chunk_output_start": r"^\s*def\s+_stage_chunk_output_start\b",
        "_empty_resume_state": r"^\s*def\s+_empty_resume_state\b",
        "_stage_signature": r"^\s*def\s+_stage_signature\b",
        "_safe_stage_name": r"^\s*def\s+_safe_stage_name\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"stage file chunk rule `{label}` remains in backend/app/processing/streaming/stage_file_pipeline.py"
            )


def _check_stage_file_chunks_runtime_boundary(issues: list[str]) -> None:
    text = _read(STAGE_FILE_CHUNKS)
    forbidden_patterns = {
        "run_stage_chunk_to_file": r"^\s*def\s+run_stage_chunk_to_file\b",
        "chunk_progress_adapter": r"^\s*def\s+chunk_progress_adapter\b",
        "stage_chunk_output_start": r"^\s*def\s+stage_chunk_output_start\b",
        "queue import": r"^\s*import\s+queue\b",
        "tempfile import": r"^\s*import\s+tempfile\b",
        "threading import": r"^\s*import\s+threading\b",
        "StageWorkerConfig": r"\bStageWorkerConfig\b",
        "read_rgb_frame": r"\bread_rgb_frame\b",
        "spawn_stage_workers": r"\bspawn_stage_workers\b",
        "write_decoded_frames_to_worker": r"\bwrite_decoded_frames_to_worker\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"stage file chunk runtime `{label}` remains in backend/app/processing/streaming/stage_file_chunks.py"
            )


def _check_stage_file_chunk_runtime_encoding_boundary(issues: list[str]) -> None:
    text = _read(STAGE_FILE_CHUNK_RUNTIME)
    forbidden_patterns = {
        "rgb frame reader": r"\bread_rgb_frame\b",
        "segment frame count resolver": r"\bresolve_segment_output_frame_count\b",
        "rawvideo encoder open": r"\bopen_rawvideo_encoder\b",
        "writer frame write": r"\bwrite_frame\s*\(",
        "written frame counter": r"\bwritten_frames\b",
        "frame count mismatch": r"Stage chunk output frame count mismatch",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"stage file chunk encoding `{label}` remains in "
                "backend/app/processing/streaming/stage_file_chunk_runtime.py"
            )


def _check_stage_worker_execution_boundary(issues: list[str]) -> None:
    text = _read(STAGE_WORKER)
    forbidden_patterns = {
        "_run_sequence_stage": r"^\s*def\s+_run_sequence_stage\b",
        "_run_interpolation_stage": r"^\s*def\s+_run_interpolation_stage\b",
        "_run_single_frame_stage": r"^\s*def\s+_run_single_frame_stage\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"stage worker execution rule `{label}` remains in backend/app/processing/streaming/stage_worker.py"
            )


def _check_stage_worker_config_boundary(issues: list[str]) -> None:
    text = _read(STAGE_WORKER)
    forbidden_patterns = {
        "config dataclass": r"^\s*class\s+StageWorkerConfig\b",
        "config mapping parser": r"^\s+def\s+from_mapping\b",
        "config json parser": r"^\s+def\s+from_json_file\b",
        "config serializer": r"^\s+def\s+to_jsonable\b",
        "processing step normalizer": r"\bnormalize_processing_step\b",
        "json config parsing": r"\bjson\.load\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"stage worker config `{label}` remains in {_rel(STAGE_WORKER)}")


def _check_streaming_pipeline_rule_boundary(issues: list[str]) -> None:
    text = _read(STREAMING_PIPELINE)
    forbidden_patterns = {
        "_build_config_snapshot": r"^\s*def\s+_build_config_snapshot\b",
        "_should_use_stage_file_pipeline": r"^\s*def\s+_should_use_stage_file_pipeline\b",
        "_stage_file_resume_source_frames": r"^\s*def\s+_stage_file_resume_source_frames\b",
        "_resolved_stream_fps": r"^\s*def\s+_resolved_stream_fps\b",
        "_resolved_output_dimensions": r"^\s*def\s+_resolved_output_dimensions\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"streaming pipeline rule `{label}` remains in backend/app/processing/streaming/pipeline.py")


def _check_streaming_pipeline_raw_boundary(issues: list[str]) -> None:
    text = _read(STREAMING_PIPELINE)
    forbidden_patterns = {
        "queue import": r"^\s*import\s+queue\b",
        "threading import": r"^\s*import\s+threading\b",
        "queue allocation": r"\bqueue\.Queue\b",
        "thread allocation": r"\bthreading\.Thread\b",
        "stop event allocation": r"\bthreading\.Event\b",
        "_encoder_worker": r"\b_encoder_worker\b",
        "encoder_thread": r"\bencoder_thread\b",
        "encode_queue": r"\bencode_queue\s*=",
        "error_queue": r"\berror_queue\s*=",
        "stop_event": r"\bstop_event\s*=",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"raw pipeline runtime `{label}` remains in backend/app/processing/streaming/pipeline.py")


def _check_pipeline_raw_runtime_boundary(issues: list[str]) -> None:
    text = _read(PIPELINE_RAW)
    forbidden_patterns = {
        "queue import": r"^\s*import\s+queue\b",
        "threading import": r"^\s*import\s+threading\b",
        "encoder worker import": r"\b_encoder_worker\b",
        "queue allocation": r"\bqueue\.Queue\b",
        "thread allocation": r"\bthreading\.Thread\b",
        "stop event allocation": r"\bthreading\.Event\b",
        "encoder thread": r"\bencoder_thread\b",
        "encode queue": r"\bencode_queue\s*=",
        "error queue": r"\berror_queue\s*=",
        "stop event": r"\bstop_event\s*=",
        "thread join": r"\.join\s*\(",
        "completed segments aggregation": r"\bread_completed_segments\s*\(",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"pipeline raw runtime `{label}` remains in {_rel(PIPELINE_RAW)}")


def _check_pipeline_raw_runtime_encoder_boundary(issues: list[str]) -> None:
    text = _read(PIPELINE_RAW_RUNTIME)
    forbidden_patterns = {
        "private encoder worker import": r"from\s+app\.processing\.streaming\.encoder\s+import\s+_encoder_worker\b",
        "private encoder worker target": r"\btarget\s*=\s*_encoder_worker\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"pipeline raw encoder worker `{label}` remains in {_rel(PIPELINE_RAW_RUNTIME)}")


def _check_streaming_pipeline_lifecycle_boundary(issues: list[str]) -> None:
    text = _read(STREAMING_PIPELINE)
    forbidden_patterns = {
        "resume conflict": r"\bResumeConflictError\b",
        "manifest prepare": r"\.prepare\s*\(",
        "decision conflict branch": r"\bdecision\.kind\b",
        "finalize helper": r"\b_finalize_segmented_output\b",
        "manifest cleanup": r"\.cleanup\s*\(",
        "final frame count": r"\bget_frame_count\s*\(",
        "resume status emitter": r"^\s*def\s+_emit_resume_status_event\b",
        "ndjson resume status": r"\bresume_status\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"streaming pipeline lifecycle `{label}` remains in backend/app/processing/streaming/pipeline.py"
            )


def _check_streaming_pipeline_preflight_boundary(issues: list[str]) -> None:
    text = _read(STREAMING_PIPELINE)
    forbidden_patterns = {
        "normalize processing steps": r"\bnormalize_processing_steps\b",
        "resolve video info": r"\bresolve_video_info\b",
        "build stage plan": r"\bbuild_stage_plan\b",
        "build signature": r"\bbuild_signature\b",
        "config snapshot": r"\bbuild_config_snapshot\b",
        "stage-file strategy": r"\bshould_use_stage_file_pipeline\b",
        "stage-file resume domain": r"\bstage_file_resume_source_frames\b",
        "output dimensions": r"\bresolved_output_dimensions\b",
        "direct pipeline rules import": r"from\s+app\.processing\.streaming\.pipeline_rules\s+import\b",
        "segment frame normalization": r"\bsegment_frames\s*=\s*max\s*\(",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text):
            issues.append(
                f"streaming pipeline preflight `{label}` remains in backend/app/processing/streaming/pipeline.py"
            )


def _check_streaming_pipeline_dispatch_boundary(issues: list[str]) -> None:
    text = _read(STREAMING_PIPELINE)
    forbidden_patterns = {
        "raw pipeline import": r"from\s+app\.processing\.streaming\.pipeline_raw\s+import\b",
        "stage file pipeline import": r"from\s+app\.processing\.streaming\.stage_file_pipeline\s+import\b",
        "worker pipeline import": r"from\s+app\.processing\.streaming\.worker_pipeline\s+import\b",
        "resume status dispatch": r"\bemit_resume_status_event\b",
        "dispatch helper": r"^\s*def\s+_run_streaming_pipeline\b",
        "raw pipeline call": r"\brun_raw_streaming_pipeline\b",
        "stage file pipeline call": r"\brun_stage_file_pipeline\b",
        "stage worker runner": r"\brun_stage_worker_pipeline\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"streaming pipeline dispatch `{label}` remains in backend/app/processing/streaming/pipeline.py"
            )


def _check_encoder_helper_boundary(issues: list[str]) -> None:
    if ENCODER.exists():
        encoder_text = _read(ENCODER)
        if "run_encoder_worker as _encoder_worker" in encoder_text:
            issues.append(f"obsolete encoder compatibility entrypoint remains in {_rel(ENCODER)}")
        forbidden_encoder_defs = {
            "segment progress callback": r"^\s*def\s+_make_segment_progress_callback\b",
            "segment frame count": r"^\s*def\s+_resolve_segment_output_frame_count\b",
            "segmented finalization": r"^\s*def\s+_finalize_segmented_output\b",
        }
        for label, pattern in forbidden_encoder_defs.items():
            if re.search(pattern, encoder_text, re.MULTILINE):
                issues.append(f"encoder helper `{label}` remains in backend/app/processing/streaming/encoder.py")

    private_helpers = (
        "_make_segment_progress_callback",
        "_resolve_segment_output_frame_count",
        "_finalize_segmented_output",
    )
    for path in (PIPELINE_LIFECYCLE, STAGE_FILE_PIPELINE, STAGE_FILE_CHUNK_RUNTIME):
        text = _read(path)
        if "from app.processing.streaming.encoder import" not in text:
            continue
        leaked = [helper for helper in private_helpers if helper in text]
        for helper in leaked:
            issues.append(f"encoder helper `{helper}` dependency remains in {_rel(path)}")


def _check_encoder_segment_writer_boundary(issues: list[str]) -> None:
    text = _read(ENCODER_WORKER)
    forbidden_patterns = {
        "Path import": r"^\s*from\s+pathlib\s+import\s+Path\b",
        "os import": r"^\s*import\s+os\b",
        "rawvideo encoder open": r"\bopen_rawvideo_encoder\b",
        "writer frame write": r"\bwriter\.write_frame\s*\(",
        "writer close": r"\bwriter\.close\s*\(",
        "manifest finalize": r"\bfinalize_chunk\s*\(",
        "chunk tmp path": r"\bchunk_tmp_path\s*\(",
        "progress callback helper": r"\b_make_segment_progress_callback\b|\bmake_segment_progress_callback\b",
        "segment frame count resolver": r"\b_resolve_segment_output_frame_count\b|\bresolve_segment_output_frame_count\b",
        "segment temp cleanup": r"\bunlink\s*\(",
        "segment writer state": r"\bcurrent_segment_input_frames\b|\bsegment_index\b|\btmp_path\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"encoder segment writer `{label}` remains in backend/app/processing/streaming/encoder.py")


def _check_processor_algorithm_boundary(issues: list[str]) -> None:
    text = _read(PROCESSOR)
    forbidden_patterns = {
        "_PipelineAlgorithms": r"^\s*class\s+_PipelineAlgorithms\b",
        "_initialize_algorithms": r"^\s*def\s+_initialize_algorithms\b",
        "_pipeline_needs_sequence": r"^\s*def\s+_pipeline_needs_sequence\b",
        "_ordered_algorithm_entries": r"^\s*def\s+_ordered_algorithm_entries\b",
        "_resolve_processor_mode": r"^\s*def\s+_resolve_processor_mode\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"processor algorithm rule `{label}` remains in backend/app/processing/streaming/processor.py"
            )


def _check_processor_stage_execution_boundary(issues: list[str]) -> None:
    text = _read(PROCESSOR)
    forbidden_patterns = {
        "_apply_pre_steps": r"^\s*def\s+_apply_pre_steps\b",
        "_apply_post_steps": r"^\s*def\s+_apply_post_steps\b",
        "_apply_stage_chain": r"^\s*def\s+_apply_stage_chain\b",
        "_run_sequence_stage": r"^\s*def\s+_run_sequence_stage\b",
        "_run_interpolation_sequence_stage": r"^\s*def\s+_run_interpolation_sequence_stage\b",
        "_run_per_frame_sequence_stage": r"^\s*def\s+_run_per_frame_sequence_stage\b",
        "_emit_stage_progress": r"^\s*def\s+_emit_stage_progress\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"processor stage execution rule `{label}` remains in backend/app/processing/streaming/processor.py"
            )


def _check_processor_stream_boundary(issues: list[str]) -> None:
    text = _read(PROCESSOR)
    forbidden_patterns = {
        "_process_single_frame_stream": r"^\s*def\s+_process_single_frame_stream\b",
        "_process_interpolated_stream": r"^\s*def\s+_process_interpolated_stream\b",
        "_process_sequence_stream": r"^\s*def\s+_process_sequence_stream\b",
        "_emit_encoded_payload": r"^\s*def\s+_emit_encoded_payload\b",
        "_drain_decoded": r"^\s*def\s+_drain_decoded\b",
        "_emit_stream_end": r"^\s*def\s+_emit_stream_end\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(f"processor stream rule `{label}` remains in backend/app/processing/streaming/processor.py")


def _check_processor_private_reexport_boundary(issues: list[str]) -> None:
    text = _read(PROCESSOR)
    forbidden_patterns = {
        "algorithm helper re-export": r"\bas\s+_(?:PipelineAlgorithms|initialize_algorithms|ordered_algorithm_entries|pipeline_needs_sequence|resolve_processor_mode)\b",
        "stage helper re-export": r"\bas\s+_(?:apply_post_steps|apply_pre_steps|apply_stage_chain|emit_stage_progress|run_interpolation_sequence_stage|run_per_frame_sequence_stage|run_sequence_stage)\b",
        "stream helper re-export": r"\bas\s+_(?:drain_decoded|emit_encoded_payload|emit_stream_end|process_interpolated_stream|process_sequence_stream|process_single_frame_stream)\b",
        "stage runtime helper re-export": r"\bas\s+_StepAlgorithm\b",
        "private helper export list": r"__all__\s*=\s*\[[^\]]*\"_(?:PipelineAlgorithms|StepAlgorithm|process_|apply_|run_|emit_|drain_|initialize_|pipeline_|ordered_)",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.DOTALL):
            issues.append(f"processor private re-export `{label}` remains in {_rel(PROCESSOR)}")


def _check_processor_stream_aggregator_boundary(issues: list[str]) -> None:
    if not PROCESSOR_STREAMS.exists():
        return

    text = _read(PROCESSOR_STREAMS)
    if "Compatibility exports" in text:
        issues.append(f"obsolete processor stream aggregator remains in {_rel(PROCESSOR_STREAMS)}")
    forbidden_patterns = {
        "process_single_frame_stream": r"^\s*def\s+process_single_frame_stream\b",
        "process_interpolated_stream": r"^\s*def\s+process_interpolated_stream\b",
        "process_sequence_stream": r"^\s*def\s+process_sequence_stream\b",
        "emit_encoded_payload": r"^\s*def\s+emit_encoded_payload\b",
        "drain_decoded": r"^\s*def\s+drain_decoded\b",
        "emit_stream_end": r"^\s*def\s+emit_stream_end\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.MULTILINE):
            issues.append(
                f"processor stream rule `{label}` remains in backend/app/processing/streaming/processor_streams.py"
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
        _check_stage_worker_runtime_boundary(issues)
        _check_stage_worker_helper_import_boundary(issues)
        _check_stage_worker_runtime_split_boundary(issues)
        _check_frontend_form_profile_rule_boundary(issues)
        _check_cli_defaults_planning_boundary(issues)
        _check_frontend_enhance_workflow_boundary(issues)
        _check_frontend_enhance_workflow_selection_boundary(issues)
        _check_frontend_enhance_workflow_lookup_boundary(issues)
        _check_frontend_enhance_rules_split_boundary(issues)
        _check_frontend_enhance_default_selection_split_boundary(issues)
        _check_frontend_enhance_view_model_boundary(issues)
        _check_frontend_enhance_view_model_split_boundary(issues)
        _check_frontend_enhance_runtime_view_split_boundary(issues)
        _check_frontend_model_metrics_barrel_boundary(issues)
        _check_frontend_enhance_binding_boundary(issues)
        _check_frontend_enhance_field_binding_boundary(issues)
        _check_frontend_enhance_field_split_boundary(issues)
        _check_frontend_enhance_projection_boundary(issues)
        _check_frontend_enhance_option_boundary(issues)
        _check_frontend_enhance_option_binding_boundary(issues)
        _check_frontend_io_view_option_boundary(issues)
        _check_frontend_io_form_rule_boundary(issues)
        _check_frontend_io_form_binding_boundary(issues)
        _check_frontend_io_form_aggregator_boundary(issues)
        _check_frontend_io_profile_state_boundary(issues)
        _check_frontend_decode_hardware_binding_boundary(issues)
        _check_frontend_defaults_workflow_boundary(issues)
        _check_frontend_encode_output_binding_boundary(issues)
        _check_worker_pipeline_plan_boundary(issues)
        _check_worker_pipeline_process_boundary(issues)
        _check_worker_pipeline_chain_runtime_boundary(issues)
        _check_worker_pipeline_file_boundary(issues)
        _check_worker_processes_event_io_boundary(issues)
        _check_worker_process_helper_import_boundary(issues)
        _check_stage_file_pipeline_chunk_boundary(issues)
        _check_stage_file_chunks_runtime_boundary(issues)
        _check_stage_file_chunk_runtime_encoding_boundary(issues)
        _check_stage_worker_execution_boundary(issues)
        _check_stage_worker_config_boundary(issues)
        _check_streaming_pipeline_rule_boundary(issues)
        _check_streaming_pipeline_raw_boundary(issues)
        _check_pipeline_raw_runtime_boundary(issues)
        _check_pipeline_raw_runtime_encoder_boundary(issues)
        _check_streaming_pipeline_lifecycle_boundary(issues)
        _check_streaming_pipeline_preflight_boundary(issues)
        _check_streaming_pipeline_dispatch_boundary(issues)
        _check_encoder_helper_boundary(issues)
        _check_encoder_segment_writer_boundary(issues)
        _check_processor_algorithm_boundary(issues)
        _check_processor_stage_execution_boundary(issues)
        _check_processor_stream_boundary(issues)
        _check_processor_private_reexport_boundary(issues)
        _check_processor_stream_aggregator_boundary(issues)
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
