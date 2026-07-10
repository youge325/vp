"""Tests for repository architecture contract checks."""

from __future__ import annotations

import importlib.util
import re
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


def test_frontend_compile_only_contracts_are_not_exported() -> None:
    contract_check = REPO_ROOT / "frontend" / "src" / "types" / "protocol" / "_contract_check.ts"
    text = contract_check.read_text(encoding="utf-8")

    assert not re.search(r"^\s*export\s+const\s+_[A-Z0-9_]+_CONTRACT\b", text, re.MULTILINE)


def test_paddlegan_disabled_model_registry_is_removed() -> None:
    weights = REPO_ROOT / "backend" / "app" / "algorithms" / "paddle" / "paddlegan_vsr" / "weights.py"
    validation = REPO_ROOT / "backend" / "app" / "planning" / "workflow_validation.py"

    assert "DISABLED_PADDLEGAN_VSR_MODELS" not in weights.read_text(encoding="utf-8")
    assert "DISABLED_PADDLEGAN_VSR_MODELS" not in validation.read_text(encoding="utf-8")


def test_package_initializers_do_not_reexport_owned_symbols() -> None:
    benchmark_init = REPO_ROOT / "backend" / "app" / "benchmark" / "__init__.py"
    paddlegan_init = REPO_ROOT / "backend" / "app" / "algorithms" / "paddle" / "paddlegan_vsr" / "__init__.py"

    assert "from app.benchmark" not in benchmark_init.read_text(encoding="utf-8")
    assert "PADDLEGAN_VSR_SPECS" not in paddlegan_init.read_text(encoding="utf-8")


def test_dead_surface_boundary_flags_reintroduced_sources(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_contract_check = tmp_path / "_contract_check.ts"
    fake_weights = tmp_path / "weights.py"
    fake_validation = tmp_path / "workflow_validation.py"
    fake_benchmark_init = tmp_path / "benchmark_init.py"
    fake_paddlegan_init = tmp_path / "paddlegan_init.py"
    fake_processing_init = tmp_path / "processing_init.py"
    fake_algorithm_factory = tmp_path / "factory.py"
    fake_stage_file_rules = tmp_path / "stage_file_rules.py"
    fake_paddle_package = tmp_path / "paddle_init.py"
    fake_pytorch_package = tmp_path / "pytorch_init.py"
    fake_contract_check.write_text("export const _TASK_REQUEST_CONTRACT = {}\n", encoding="utf-8")
    fake_weights.write_text(
        "DISABLED_PADDLEGAN_VSR_MODELS = {}\n"
        "def resolve_auxiliary_weight_path(filename):\n    pass\n"
        "def ensure_auxiliary_weight_file(model_id, filename):\n    pass\n",
        encoding="utf-8",
    )
    fake_validation.write_text("if algorithm in DISABLED_PADDLEGAN_VSR_MODELS:\n    pass\n", encoding="utf-8")
    fake_benchmark_init.write_text("from app.benchmark.runner import run_benchmark\n", encoding="utf-8")
    fake_paddlegan_init.write_text(
        "from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS\n",
        encoding="utf-8",
    )
    fake_processing_init.write_text("def register_default_algorithms():\n    pass\n", encoding="utf-8")
    fake_algorithm_factory.write_text(
        'message = "call register_default_algorithms() first"\n',
        encoding="utf-8",
    )
    fake_stage_file_rules.write_text("def empty_resume_state():\n    pass\n", encoding="utf-8")
    fake_paddle_package.write_text("__all__: list[str] = []\n", encoding="utf-8")
    fake_pytorch_package.write_text("__all__: list[str] = []\n", encoding="utf-8")
    monkeypatch.setattr(module, "FRONTEND_PROTOCOL_CONTRACT_CHECK", fake_contract_check, raising=False)
    monkeypatch.setattr(module, "PADDLEGAN_WEIGHTS", fake_weights, raising=False)
    monkeypatch.setattr(module, "WORKFLOW_VALIDATION", fake_validation, raising=False)
    monkeypatch.setattr(module, "BENCHMARK_PACKAGE", fake_benchmark_init, raising=False)
    monkeypatch.setattr(module, "PADDLEGAN_VSR_PACKAGE", fake_paddlegan_init, raising=False)
    monkeypatch.setattr(module, "PROCESSING_PACKAGE", fake_processing_init, raising=False)
    monkeypatch.setattr(module, "ALGORITHM_FACTORY", fake_algorithm_factory, raising=False)
    monkeypatch.setattr(module, "STAGE_FILE_RULES", fake_stage_file_rules, raising=False)
    monkeypatch.setattr(module, "PADDLE_PACKAGE", fake_paddle_package, raising=False)
    monkeypatch.setattr(module, "PYTORCH_PACKAGE", fake_pytorch_package, raising=False)
    issues: list[str] = []

    getattr(module, "_check_dead_surface_boundary", lambda _issues: None)(issues)

    assert len(issues) == 11, issues


def test_production_processing_has_no_global_algorithm_bootstrap() -> None:
    processing_init = REPO_ROOT / "backend" / "app" / "processing" / "__init__.py"
    algorithm_factory = REPO_ROOT / "backend" / "app" / "algorithms" / "factory.py"

    assert "register_default_algorithms" not in processing_init.read_text(encoding="utf-8")
    assert "register_default_algorithms" not in algorithm_factory.read_text(encoding="utf-8")


def test_single_use_helpers_and_empty_package_exports_are_removed() -> None:
    weights = REPO_ROOT / "backend" / "app" / "algorithms" / "paddle" / "paddlegan_vsr" / "weights.py"
    stage_file_rules = REPO_ROOT / "backend" / "app" / "processing" / "streaming" / "stage_file_rules.py"
    paddle_package = REPO_ROOT / "backend" / "app" / "algorithms" / "paddle" / "__init__.py"
    pytorch_package = REPO_ROOT / "backend" / "app" / "algorithms" / "pytorch" / "__init__.py"

    weights_text = weights.read_text(encoding="utf-8")
    assert "resolve_auxiliary_weight_path" not in weights_text
    assert "ensure_auxiliary_weight_file" not in weights_text
    assert "empty_resume_state" not in stage_file_rules.read_text(encoding="utf-8")
    assert "__all__" not in paddle_package.read_text(encoding="utf-8")
    assert "__all__" not in pytorch_package.read_text(encoding="utf-8")


def test_paddlegan_vsr_contract_matches_current_repo() -> None:
    module = _load_module()
    backend_specs = module._collect_backend_paddlegan_enabled_models()
    algorithm_metadata = module._collect_backend_algorithm_metadata()

    issues = module._diff_paddlegan_vsr_contract(backend_specs, algorithm_metadata)

    assert backend_specs == ALL_PADDLEGAN_VSR_MODELS
    assert {
        name for name, metadata in algorithm_metadata.items() if metadata["family"] == "paddlegan_vsr"
    } == backend_specs
    assert issues == []


def test_paddlegan_vsr_contract_flags_missing_metadata() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"ppmsvsr", "edvr"},
        algorithm_metadata={
            "ppmsvsr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "editable_chunk"},
        },
    )

    assert any("edvr" in issue and "metadata" in issue.lower() for issue in issues), issues


def test_paddlegan_vsr_contract_flags_wrong_metadata_shape() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"edvr"},
        algorithm_metadata={
            "edvr": {"family": "paddlegan_vsr", "fixedScaleFactor": 2, "inputFrameMode": "editable_chunk"},
        },
    )

    assert any("fixedScaleFactor" in issue and "edvr" in issue for issue in issues), issues
    assert any("inputFrameMode" in issue and "edvr" in issue for issue in issues), issues


def test_stage_worker_does_not_import_processor_private_helpers() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_stage_worker_private_import_boundary(issues)

    assert issues == []


def test_stage_worker_private_import_boundary_flags_private_processor_dependency(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker = tmp_path / "stage_worker.py"
    fake_stage_worker.write_text(
        "from app.processing.streaming.processor import _StepAlgorithm, _run_stage\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER", fake_stage_worker)
    issues: list[str] = []

    module._check_stage_worker_private_import_boundary(issues)

    assert any("processor private helpers" in issue for issue in issues), issues


def test_cli_process_validation_compat_boundary_flags_legacy_wrappers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_validation = tmp_path / "_process_validation.py"
    fake_validation.write_text(
        "def _load_json_arg():\n"
        "    pass\n\n"
        "def load_configs():\n"
        "    pass\n\n"
        "def collect_config_sections(args):\n"
        "    return {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CLI_PROCESS_VALIDATION", fake_validation, raising=False)
    issues: list[str] = []

    module._check_cli_process_validation_compat_boundary(issues)

    assert any("CLI process validation compatibility" in issue for issue in issues), issues
    assert any("collect_config_sections" in issue for issue in issues), issues


def test_dll_paths_test_helper_boundary_flags_production_reset_helper(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_dll_paths = tmp_path / "dll_paths.py"
    fake_dll_paths.write_text("def reset_registry_for_tests():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(module, "DLL_PATHS", fake_dll_paths, raising=False)
    issues: list[str] = []

    module._check_dll_paths_test_helper_boundary(issues)

    assert any("DLL path test helper" in issue for issue in issues), issues


def test_backend_model_metrics_has_no_obsolete_attribute_int_helper() -> None:
    model_metrics = REPO_ROOT / "backend" / "app" / "utils" / "model_metrics.py"

    assert "def _attribute_int(" not in model_metrics.read_text(encoding="utf-8")


def test_backend_model_metrics_dead_helper_boundary_flags_obsolete_attribute_helper(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_model_metrics = tmp_path / "model_metrics.py"
    fake_model_metrics.write_text("def _attribute_int(node, name, default):\n    return default\n", encoding="utf-8")
    monkeypatch.setattr(module, "BACKEND_MODEL_METRICS", fake_model_metrics, raising=False)
    issues: list[str] = []

    module._check_backend_model_metrics_dead_helper_boundary(issues)

    assert any("model metrics dead helper" in issue for issue in issues), issues


def test_backend_opencv_runtime_dead_helper_boundary_flags_cuda_count_helper(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_opencv_runtime = tmp_path / "opencv_runtime.py"
    fake_opencv_runtime.write_text(
        "def get_cuda_device_count():\n    return 0\n\n__all__ = ['get_cuda_device_count', 'import_cv2']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BACKEND_OPENCV_RUNTIME", fake_opencv_runtime, raising=False)
    issues: list[str] = []

    module._check_backend_opencv_runtime_dead_helper_boundary(issues)

    assert any("get_cuda_device_count" in issue for issue in issues), issues


def test_dead_type_aliases_do_not_remain_in_current_repo() -> None:
    backend_onnx_models = REPO_ROOT / "backend" / "app" / "utils" / "onnx_models.py"
    workflow_types = REPO_ROOT / "frontend" / "src" / "types" / "domain" / "workflow.ts"
    media_types = REPO_ROOT / "frontend" / "src" / "types" / "domain" / "media.ts"
    env_types = REPO_ROOT / "frontend" / "src" / "types" / "domain" / "env.ts"
    capability_types = REPO_ROOT / "frontend" / "src" / "types" / "domain" / "capability.ts"

    assert "OnnxEngine =" not in backend_onnx_models.read_text(encoding="utf-8")
    workflow_text = workflow_types.read_text(encoding="utf-8")
    assert "export type WorkflowMode" not in workflow_text
    assert "export type EditingScope" not in workflow_text
    assert "export type ItemConfigSnapshot" not in media_types.read_text(encoding="utf-8")
    env_text = env_types.read_text(encoding="utf-8")
    assert "export interface ResourceSummary" not in env_text
    assert "export type ModelAnalysisStatus" not in env_text
    assert "export interface ModelMetricInfo" not in env_text
    capability_text = capability_types.read_text(encoding="utf-8")
    assert "export type CapabilityOptionType" not in capability_text
    assert "export interface CapabilityChoice" not in capability_text


def test_backend_dead_algorithm_helper_boundary_matches_current_repo() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_backend_dead_algorithm_helper_boundary(issues)

    assert issues == []


def test_backend_dead_algorithm_helper_boundary_flags_unused_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_payload = tmp_path / "frame_payload.py"
    fake_factory = tmp_path / "factory.py"
    fake_payload.write_text(
        "class FramePayload:\n"
        "    def has_tensor_for(self, backend): return False\n"
        "    def _ensure_backend_matches(self, backend): return None\n\n"
        "def _backend_label(backend): return str(backend)\n",
        encoding="utf-8",
    )
    fake_factory.write_text(
        "class AlgorithmFactory:\n    def get_available_algorithms(self): return {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRAME_PAYLOAD", fake_payload, raising=False)
    monkeypatch.setattr(module, "ALGORITHM_FACTORY", fake_factory, raising=False)
    issues: list[str] = []

    module._check_backend_dead_algorithm_helper_boundary(issues)

    assert any("has_tensor_for" in issue for issue in issues), issues
    assert any("_ensure_backend_matches" in issue for issue in issues), issues
    assert any("_backend_label" in issue for issue in issues), issues
    assert any("get_available_algorithms" in issue for issue in issues), issues


def test_enhance_runtime_rows_requires_precomputed_frame_state() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_frontend_enhance_runtime_rows_boundary(issues)

    assert issues == []


def test_enhance_runtime_rows_boundary_flags_recomputed_frame_state(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime_rows = tmp_path / "enhance-runtime-rows.ts"
    fake_runtime_rows.write_text(
        "interface Input { frameState?: EnhanceRuntimeFrameState }\n"
        "const resolvedFrameState = frameState ?? buildEnhanceRuntimeFrameState(input)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_RUNTIME_ROWS", fake_runtime_rows, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_runtime_rows_boundary(issues)

    assert any("optional precomputed frame state" in issue for issue in issues), issues
    assert any("precomputed frame state fallback" in issue for issue in issues), issues


def test_dead_type_alias_boundary_flags_obsolete_aliases(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_onnx_models = tmp_path / "onnx_models.py"
    fake_workflow_types = tmp_path / "workflow.ts"
    fake_media_types = tmp_path / "media.ts"
    fake_env_types = tmp_path / "env.ts"
    fake_capability_types = tmp_path / "capability.ts"
    fake_onnx_models.write_text(
        "OnnxEngine = Literal['cuda']\n\n"
        "def get_onnx_model_dir(kind, model_root=None):\n"
        "    return model_root / kind\n",
        encoding="utf-8",
    )
    fake_workflow_types.write_text(
        "export type WorkflowMode = 'frame_interpolation'\nexport type EditingScope = 'preset'\n",
        encoding="utf-8",
    )
    fake_media_types.write_text(
        "export type ItemConfigSnapshot = Pick<WorkbenchPreset, 'decodeConfig'>\n", encoding="utf-8"
    )
    fake_env_types.write_text(
        "export interface ResourceSummary {}\n"
        "export type ModelAnalysisStatus = 'ok'\n"
        "export interface ModelMetricInfo {}\n",
        encoding="utf-8",
    )
    fake_capability_types.write_text(
        "export type CapabilityOptionType = 'choice'\nexport interface CapabilityChoice {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BACKEND_ONNX_MODELS", fake_onnx_models, raising=False)
    monkeypatch.setattr(module, "DOMAIN_WORKFLOW_TYPES", fake_workflow_types, raising=False)
    monkeypatch.setattr(module, "DOMAIN_MEDIA_TYPES", fake_media_types, raising=False)
    monkeypatch.setattr(module, "DOMAIN_ENV_TYPES", fake_env_types, raising=False)
    monkeypatch.setattr(module, "DOMAIN_CAPABILITY_TYPES", fake_capability_types, raising=False)
    issues: list[str] = []

    module._check_dead_type_alias_boundary(issues)

    assert any("OnnxEngine" in issue for issue in issues), issues
    assert any("get_onnx_model_dir" in issue for issue in issues), issues
    assert any("WorkflowMode" in issue for issue in issues), issues
    assert any("EditingScope" in issue for issue in issues), issues
    assert any("ItemConfigSnapshot" in issue for issue in issues), issues
    assert any("ResourceSummary" in issue for issue in issues), issues
    assert any("ModelAnalysisStatus" in issue for issue in issues), issues
    assert any("ModelMetricInfo" in issue for issue in issues), issues
    assert any("CapabilityOptionType" in issue for issue in issues), issues
    assert any("CapabilityChoice" in issue for issue in issues), issues


def test_frontend_task_event_reducers_have_no_dead_payload_params() -> None:
    reducer = REPO_ROOT / "frontend" / "src" / "services" / "task" / "events.ts"
    text = reducer.read_text(encoding="utf-8")

    assert "TaskProgressPayload" not in text
    assert "TaskCompletedPayload" not in text
    assert "applyTaskProgress(state: MediaTaskState, _payload" not in text
    assert "applyTaskCompleted(state: MediaTaskState, _payload" not in text


def test_frontend_task_event_reducer_payload_boundary_flags_dead_payload_params(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_reducer = tmp_path / "events.ts"
    fake_reducer.write_text(
        "import type { TaskCompletedPayload, TaskProgressPayload } from '@/types/protocol'\n"
        "export function applyTaskProgress(state: MediaTaskState, _payload: TaskProgressPayload) { return state }\n"
        "export function applyTaskCompleted(state: MediaTaskState, _payload: TaskCompletedPayload) { return state }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "TASK_EVENT_REDUCERS", fake_reducer, raising=False)
    issues: list[str] = []

    module._check_frontend_task_event_reducer_payload_boundary(issues)

    assert any("task event reducer payload" in issue for issue in issues), issues


def test_collect_typed_ipc_contract_args_allows_private_mapping(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_contract = tmp_path / "contract.ts"
    fake_contract.write_text(
        "type TaskControlKind = 'pause' | 'resume'\n"
        "interface IpcCommandArgs {\n"
        "  pick_inputs: undefined\n"
        "  control_task: { kind: TaskControlKind }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "IPC_CONTRACT", fake_contract, raising=False)

    assert module._collect_typed_ipc_contract_args() == {
        "pick_inputs": set(),
        "control_task": {"kind"},
    }


def test_frontend_ipc_contract_uses_args_mapping_as_command_source() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_frontend_ipc_contract_surface_boundary(issues)

    assert issues == []


def test_frontend_ipc_contract_surface_boundary_flags_handwritten_command_union(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_contract = tmp_path / "contract.ts"
    fake_contract.write_text(
        "export type IpcCommand = 'pick_inputs' | 'control_task'\n"
        "interface IpcCommandArgs { pick_inputs: undefined; control_task: { kind: string } }\n"
        "interface IpcCommandResult { pick_inputs: string[]; control_task: void }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "IPC_CONTRACT", fake_contract, raising=False)
    issues: list[str] = []

    module._check_frontend_ipc_contract_surface_boundary(issues)

    assert any("keyof command source" in issue for issue in issues), issues


def test_frontend_ipc_contract_surface_boundary_flags_private_command_name_list(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_contract = tmp_path / "contract.ts"
    fake_contract.write_text(
        "const IPC_COMMAND_NAMES = ['pick_inputs'] as const\n"
        "export type IpcCommand = typeof IPC_COMMAND_NAMES[number]\n"
        "interface IpcCommandArgs { pick_inputs: undefined }\n"
        "interface IpcCommandResult { pick_inputs: string[] }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "IPC_CONTRACT", fake_contract, raising=False)
    issues: list[str] = []

    module._check_frontend_ipc_contract_surface_boundary(issues)

    assert any("command name list" in issue for issue in issues), issues


def test_frontend_ipc_contract_surface_boundary_flags_internal_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_contract = tmp_path / "contract.ts"
    fake_contract.write_text(
        "export const IPC_COMMAND_NAMES = ['pick_inputs'] as const\n"
        "export type IpcCommand = typeof IPC_COMMAND_NAMES[number]\n"
        "export type TaskControlKind = 'pause' | 'resume'\n"
        "export interface IpcCommandArgs { pick_inputs: undefined }\n"
        "export interface IpcCommandResult { pick_inputs: string[] }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "IPC_CONTRACT", fake_contract, raising=False)
    issues: list[str] = []

    module._check_frontend_ipc_contract_surface_boundary(issues)

    assert any("IPC_COMMAND_NAMES" in issue for issue in issues), issues
    assert any("TaskControlKind" in issue for issue in issues), issues
    assert any("IpcCommandArgs" in issue for issue in issues), issues
    assert any("IpcCommandResult" in issue for issue in issues), issues


def test_cli_process_execution_has_no_format_conversion_dead_config_unpack() -> None:
    process_execution = REPO_ROOT / "backend" / "app" / "cli" / "commands" / "_process_execution.py"
    text = process_execution.read_text(encoding="utf-8")

    assert "_workflow_config" not in text
    assert "_output_config" not in text


def test_cli_process_execution_dead_config_unpack_boundary_flags_dead_unpack(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_execution = tmp_path / "_process_execution.py"
    fake_execution.write_text(
        "def _run_format_conversion(configs):\n"
        "    decode_config, encode_config, _workflow_config, _output_config = configs.legacy_tuple()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CLI_PROCESS_EXECUTION", fake_execution, raising=False)
    issues: list[str] = []

    module._check_cli_process_execution_dead_config_unpack_boundary(issues)

    assert any("dead config unpack" in issue for issue in issues), issues


def test_cli_defaults_planning_boundary_flags_model_path_helper(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "defaults.py"
    fake_defaults.write_text(
        "from pathlib import Path\n\n"
        "def _model_path(model_version=None):\n"
        "    return Path('models') / f'flownet_v{model_version}.pkl'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CLI_DEFAULTS", fake_defaults, raising=False)
    issues: list[str] = []

    module._check_cli_defaults_planning_boundary(issues)

    assert any("model path helper" in issue for issue in issues), issues


def test_backend_tests_private_cli_defaults_boundary_flags_private_default_import(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_tests = tmp_path / "tests"
    fake_tests.mkdir()
    (fake_tests / "test_cli.py").write_text(
        "from app.cli.defaults import _default_output_config\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BACKEND_TESTS", fake_tests, raising=False)
    issues: list[str] = []

    module._check_backend_test_private_cli_defaults_boundary(issues)

    assert any("private CLI defaults import" in issue for issue in issues), issues


def test_segment_manifest_compat_boundary_flags_completed_segments_shim(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_manifest = tmp_path / "manifest.py"
    fake_manifest.write_text(
        "class SegmentManifest:\n    def read_completed_segments(self):\n        return self.scan_completed_chunks()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "SEGMENT_MANIFEST", fake_manifest, raising=False)
    issues: list[str] = []

    module._check_segment_manifest_compat_boundary(issues)

    assert any("SegmentManifest compatibility shim" in issue for issue in issues), issues


def test_segment_manifest_boundary_flags_local_json_persistence(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_manifest = tmp_path / "manifest.py"
    fake_manifest.write_text(
        "import json\n"
        "class SegmentManifest:\n"
        "    def _write_manifest(self, payload):\n"
        "        json.dump(payload, self.manifest_path)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "SEGMENT_MANIFEST", fake_manifest, raising=False)
    issues: list[str] = []

    module._check_segment_manifest_compat_boundary(issues)

    assert any("SegmentManifest persistence" in issue for issue in issues), issues


def test_enhance_form_workflow_rule_boundary_flags_mutation_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_form = tmp_path / "useEnhanceForm.ts"
    fake_form.write_text("pickDefaultInterpolationAlgorithm(env, 'onnx')\n", encoding="utf-8")
    monkeypatch.setattr(module, "ENHANCE_FORM", fake_form)
    issues: list[str] = []

    module._check_frontend_enhance_workflow_boundary(issues)

    assert any("enhance workflow rule" in issue for issue in issues), issues


def test_frontend_enhance_workflow_selection_boundary_flags_local_selection_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_workflow = tmp_path / "enhance-workflow.ts"
    fake_workflow.write_text(
        "const TENSOR_BACKENDS = ['pytorch', 'paddle', 'onnx']\n"
        "function findInterpolationAlgorithm() {}\n"
        "function findSuperResolutionAlgorithm() {}\n"
        "function pickSupportedBackend() {}\n"
        "function preferOnnxInterpolationForPaddleSuperResolution() {}\n"
        "fallbackInterpolationOnnxModel(env, algorithm)\n"
        "fallbackSuperResolutionOnnxModel(env, algorithm)\n"
        "fixedRuntimeFrameCount(algorithm)\n"
        "fixedSuperResolutionScaleFactor(algorithm)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_WORKFLOW", fake_workflow)
    issues: list[str] = []

    module._check_frontend_enhance_workflow_selection_boundary(issues)

    assert any("enhance workflow selection" in issue for issue in issues), issues


def test_frontend_enhance_workflow_selection_boundary_flags_pass_through_wrappers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_workflow = tmp_path / "enhance-workflow.ts"
    fake_workflow.write_text(
        "export function applyInterpolationBackendSelection(config, value, checkResult) {\n"
        "  applyInterpolationBackendSelectionDefaults(config, value, checkResult)\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_WORKFLOW", fake_workflow)
    issues: list[str] = []

    module._check_frontend_enhance_workflow_selection_boundary(issues)

    assert any("selection pass-through" in issue for issue in issues), issues


def test_frontend_enhance_workflow_lookup_boundary_flags_local_lookup_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_selection = tmp_path / "enhance-workflow-selection.ts"
    fake_selection.write_text(
        "const TENSOR_BACKENDS = ['pytorch', 'paddle', 'onnx']\n"
        "function isTensorBackend(value) { return true }\n"
        "export function findInterpolationAlgorithm() {}\n"
        "export function findSuperResolutionAlgorithm() {}\n"
        "export function pickSupportedBackend() {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_WORKFLOW_SELECTION", fake_selection, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_workflow_lookup_boundary(issues)

    assert any("enhance workflow lookup" in issue for issue in issues), issues


def test_frontend_enhance_workflow_lookup_boundary_flags_lookup_reexport(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_selection = tmp_path / "enhance-workflow-selection.ts"
    fake_selection.write_text(
        "export {\n"
        "  findInterpolationAlgorithm,\n"
        "  findSuperResolutionAlgorithm,\n"
        "  pickSupportedBackend,\n"
        "} from './enhance-workflow-lookup'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_WORKFLOW_SELECTION", fake_selection, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_workflow_lookup_boundary(issues)

    assert any("enhance workflow lookup" in issue for issue in issues), issues


def test_frontend_enhance_removed_rule_files_boundary_flags_empty_files(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rules = tmp_path / "enhance-rules.ts"
    fake_defaults = tmp_path / "enhance-default-selection.ts"
    fake_pickers = tmp_path / "enhance-default-pickers.ts"
    fake_rules.write_text("", encoding="utf-8")
    fake_defaults.write_text("", encoding="utf-8")
    fake_pickers.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "ENHANCE_RULES", fake_rules, raising=False)
    monkeypatch.setattr(module, "ENHANCE_DEFAULT_SELECTION", fake_defaults, raising=False)
    monkeypatch.setattr(module, "ENHANCE_DEFAULT_PICKERS", fake_pickers, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_rules_split_boundary(issues)
    module._check_frontend_enhance_default_selection_split_boundary(issues)
    module._check_frontend_enhance_default_pickers_boundary(issues)

    assert any("obsolete enhance rules file" in issue for issue in issues), issues
    assert any("obsolete enhance default-selection file" in issue for issue in issues), issues
    assert any("obsolete enhance default pickers file" in issue for issue in issues), issues


def test_frontend_enhance_onnx_defaults_boundary_flags_direct_algorithm_lookup(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "enhance-onnx-defaults.ts"
    fake_defaults.write_text(
        "const interpolation = checkResult?.interpolationAlgorithms?.find((algorithm) => algorithm.name === selected)\n"
        "const superResolution = checkResult?.superResolutionAlgorithms?.find((algorithm) => algorithm.name === selected)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_ONNX_DEFAULTS", fake_defaults, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_onnx_defaults_boundary(issues)

    assert any("enhance ONNX defaults" in issue for issue in issues), issues


def test_worker_pipeline_plan_boundary_flags_local_plan_builders(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "@dataclass(frozen=True, slots=True)\n"
        "class StageWorkerPlan:\n"
        "    pass\n\n"
        "def build_stage_worker_plans():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_plan_boundary(issues)

    assert any("worker plan" in issue for issue in issues), issues


def test_worker_pipeline_plan_boundary_flags_obsolete_plan_reexports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "from app.processing.streaming.worker_plans import (\n"
        "    StageChunkPlan,\n"
        "    StageWorkerPlan,\n"
        "    boundary_schedule_for_stage_plan,\n"
        "    build_stage_chunk_plans,\n"
        "    build_stage_worker_plans,\n"
        ")\n"
        "__all__ = [\n"
        '    "StageWorkerPlan",\n'
        '    "build_stage_chunk_plans",\n'
        '    "run_stage_worker_pipeline",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_plan_boundary(issues)

    assert any("obsolete plan import" in issue for issue in issues), issues
    assert any("obsolete plan export" in issue for issue in issues), issues


def test_worker_pipeline_test_boundary_flags_pure_plan_rule_tests(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_test = tmp_path / "test_worker_pipeline.py"
    fake_test.write_text(
        "import app.processing.streaming.stage_rules as stage_rules\n"
        "from app.processing.streaming.pipeline_rules import stage_file_resume_source_frames\n"
        "from app.processing.streaming.worker_plans import build_stage_chunk_plans, build_stage_worker_plans\n\n"
        "def test_worker_plan_tracks_dimensions_for_super_resolution_then_interpolation():\n"
        "    return build_stage_worker_plans()\n\n"
        "def test_boundary_schedule_matches_interpolation_output_groups():\n"
        "    return stage_file_resume_source_frames()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE_TEST", fake_test, raising=False)
    issues: list[str] = []

    module._check_worker_pipeline_test_boundary(issues)

    assert any("worker pipeline test boundary" in issue for issue in issues), issues


def test_enhance_form_view_model_boundary_flags_derived_rule_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_form = tmp_path / "useEnhanceForm.ts"
    fake_form.write_text(
        "estimateModelRuntimeMetrics(detail, video)\nfixedRuntimeFrameCount(algorithm)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_FORM", fake_form)
    issues: list[str] = []

    module._check_frontend_enhance_view_model_boundary(issues)

    assert any("enhance view-model rule" in issue for issue in issues), issues


def test_worker_pipeline_process_boundary_flags_local_runtime_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "@dataclass(slots=True)\n"
        "class _WorkerHandle:\n"
        "    pass\n\n"
        "def _spawn_stage_workers():\n"
        "    pass\n\n"
        "def _read_worker_stderr():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_process_boundary(issues)

    assert any("worker process helper" in issue for issue in issues), issues


def test_worker_pipeline_process_boundary_flags_obsolete_event_reexport(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "from app.processing.streaming.worker_process_events import parse_stage_event_line\n"
        '__all__ = ["parse_stage_event_line", "run_stage_worker_pipeline"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_process_boundary(issues)

    assert any("parse_stage_event_line import" in issue for issue in issues), issues
    assert any("parse_stage_event_line export" in issue for issue in issues), issues


def test_worker_pipeline_chain_runtime_boundary_flags_local_thread_and_io_runtime(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "import tempfile\n"
        "import threading\n"
        "from app.processing.streaming.worker_processes import spawn_stage_workers, read_worker_stderr\n\n"
        "with tempfile.TemporaryDirectory(prefix='vp-stage-workers-') as config_dir:\n"
        "    handles = spawn_stage_workers([], config_dir=Path(config_dir), python_executable=sys.executable)\n"
        "    threading.Thread(target=read_worker_stderr)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_chain_runtime_boundary(issues)

    assert any("worker chain runtime" in issue for issue in issues), issues


def test_worker_pipeline_queue_boundary_flags_local_encode_queue_internals(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "from app.processing.streaming.queues import StreamEnd, _ENCODE_END, _queue_put, _queue_put_nowait\n"
        "_queue_put(encode_queue, StreamEnd(next_source_frame=3), stop_event)\n"
        "_queue_put_nowait(encode_queue, _ENCODE_END)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_queue_boundary(issues)

    assert any("worker pipeline encode queue" in issue for issue in issues), issues


def test_worker_processes_event_io_boundary_flags_local_event_and_rawvideo_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_processes = tmp_path / "worker_processes.py"
    fake_processes.write_text(
        "from app.processing.streaming.stage_worker import STAGE_EVENT_PREFIX, read_rgb_frame, write_rgb_frame\n"
        "from app.processing.streaming.worker_plans import boundary_schedule_for_stage_plan\n"
        "TENSORRT_LOG_PREFIX = '[VP_TRT]'\n\n"
        "def parse_stage_event_line():\n"
        "    pass\n\n"
        "def read_worker_stderr():\n"
        "    pass\n\n"
        "def write_decoded_frames_to_worker():\n"
        "    pass\n\n"
        "def drain_final_worker_output():\n"
        "    pass\n\n"
        "def close_pipe():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PROCESSES", fake_processes)
    issues: list[str] = []

    module._check_worker_processes_event_io_boundary(issues)

    assert any("worker process event/io helper" in issue for issue in issues), issues


def test_worker_processes_event_io_boundary_flags_compatibility_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_processes = tmp_path / "worker_processes.py"
    fake_processes.write_text(
        "from app.processing.streaming.worker_process_events import parse_stage_event_line, read_worker_stderr\n"
        "from app.processing.streaming.worker_process_io import (\n"
        "    close_pipe,\n"
        "    drain_final_worker_output,\n"
        "    write_decoded_frames_to_worker,\n"
        ")\n\n"
        "__all__ = [\n"
        '    "WorkerHandle",\n'
        '    "close_pipe",\n'
        '    "drain_final_worker_output",\n'
        '    "parse_stage_event_line",\n'
        '    "read_worker_stderr",\n'
        '    "spawn_stage_workers",\n'
        '    "wait_for_workers",\n'
        '    "write_decoded_frames_to_worker",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PROCESSES", fake_processes)
    issues: list[str] = []

    module._check_worker_processes_event_io_boundary(issues)

    assert any("event helper import" in issue for issue in issues), issues
    assert any("io helper import" in issue for issue in issues), issues
    assert any("helper __all__ export" in issue for issue in issues), issues


def test_worker_process_helper_import_boundary_flags_helper_imports_from_entrypoint(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_chunk_runtime = tmp_path / "stage_file_chunk_runtime.py"
    fake_chain_runtime = tmp_path / "worker_chain_runtime.py"
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_chunk_runtime.write_text(
        "from app.processing.streaming.worker_processes import (\n"
        "    close_pipe,\n"
        "    read_worker_stderr,\n"
        "    spawn_stage_workers,\n"
        ")\n",
        encoding="utf-8",
    )
    fake_chain_runtime.write_text(
        "from app.processing.streaming.worker_processes import drain_final_worker_output, write_decoded_frames_to_worker\n",
        encoding="utf-8",
    )
    fake_pipeline.write_text(
        "from app.processing.streaming.worker_processes import parse_stage_event_line\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_RUNTIME", fake_chunk_runtime, raising=False)
    monkeypatch.setattr(module, "WORKER_CHAIN_RUNTIME", fake_chain_runtime, raising=False)
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline, raising=False)
    issues: list[str] = []

    module._check_worker_process_helper_import_boundary(issues)

    assert any("worker process helper" in issue for issue in issues), issues


def test_worker_processes_test_boundary_flags_event_and_io_helper_tests(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_test = tmp_path / "test_worker_processes.py"
    fake_test.write_text(
        "from app.processing.streaming.worker_process_events import parse_stage_event_line, read_worker_stderr\n"
        "from app.processing.streaming.worker_process_io import drain_final_worker_output\n\n"
        "def test_parse_stage_event_line_returns_json_event_only_for_prefixed_lines():\n"
        "    assert parse_stage_event_line('x') is None\n\n"
        "def test_drain_final_worker_output_stops_after_expected_frame_count():\n"
        "    drain_final_worker_output()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PROCESSES_TEST", fake_test, raising=False)
    issues: list[str] = []

    module._check_worker_processes_test_boundary(issues)

    assert any("worker processes test boundary" in issue for issue in issues), issues


def test_enhance_view_option_boundary_flags_view_local_option_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_view = tmp_path / "EnhanceModuleView.vue"
    fake_view.write_text(
        "import { buildBackendOptions, toTensorBackend } from '@/services/preset/enhance-options'\n"
        "import { useGpuCapabilities } from '@/composables/selectors/useGpuCapabilities'\n"
        "import { modelOptionLabel } from '@/services/model-metrics'\n"
        "const FPS_MODE_OPTIONS = []\n"
        "const options = buildBackendOptions(backends)\n"
        "function setInterpolationBackend(value) { form.interpolationBackend = toTensorBackend(value) }\n"
        "function findDetail(details, name) { return details.find((detail) => detail.name === name) }\n"
        "form.interpolationBackend = value as TensorBackend\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_VIEW", fake_view)
    issues: list[str] = []

    module._check_frontend_enhance_option_boundary(issues)

    assert any("enhance option rule" in issue for issue in issues), issues


def test_frontend_enhance_option_binding_boundary_flags_aggregator_rule_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_bindings = tmp_path / "enhance-option-bindings.ts"
    fake_bindings.write_text(
        "import { useGpuCapabilities } from '@/composables/selectors/useGpuCapabilities'\n"
        "import { buildBackendOptions, toTensorBackend } from '@/services/preset/enhance-options'\n"
        "const backendOptions = buildBackendOptions(backends)\n"
        "function setInterpolationBackend(value) { form.interpolationBackend = toTensorBackend(value) }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_OPTION_BINDINGS", fake_bindings)
    issues: list[str] = []

    module._check_frontend_enhance_option_binding_boundary(issues)

    assert any("enhance option binding rule" in issue for issue in issues), issues


def test_worker_pipeline_file_boundary_flags_local_stage_file_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "def run_stage_file_pipeline():\n"
        "    pass\n\n"
        "def _run_single_stage_file_chunks():\n"
        "    pass\n\n"
        "def _run_stage_chunk_to_file():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_file_boundary(issues)

    assert any("stage file pipeline helper" in issue for issue in issues), issues


def test_worker_pipeline_file_boundary_flags_obsolete_stage_file_reexport(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "worker_pipeline.py"
    fake_pipeline.write_text(
        "from app.processing.streaming.stage_file_pipeline import run_stage_file_pipeline\n"
        '__all__ = ["run_stage_file_pipeline", "run_stage_worker_pipeline"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKER_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_worker_pipeline_file_boundary(issues)

    assert any("stage file pipeline import" in issue for issue in issues), issues
    assert any("stage file pipeline export" in issue for issue in issues), issues


def test_frontend_io_view_option_boundary_flags_view_local_option_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_decode_view = tmp_path / "DecodeModuleView.vue"
    fake_encode_view = tmp_path / "EncodeModuleView.vue"
    fake_decode_view.write_text(
        "visibleDecoderProfiles.value.map((profile) => ({ value: profile.name, label: profile.label }))\n",
        encoding="utf-8",
    )
    fake_encode_view.write_text(
        "import { CONTAINER_OPTIONS } from '@/config/constants'\n"
        "CONTAINER_OPTIONS.map((value) => ({ value, label: value.toUpperCase() }))\n"
        "setRateControlMode(value as RateControlMode)\n"
        "Number(editorConfig.outputConfig.segmentFrames)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "DECODE_VIEW", fake_decode_view)
    monkeypatch.setattr(module, "ENCODE_VIEW", fake_encode_view)
    issues: list[str] = []

    module._check_frontend_io_view_option_boundary(issues)

    assert any("io option rule" in issue for issue in issues), issues


def test_frontend_io_form_rule_boundary_flags_composable_rule_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_decode_form = tmp_path / "useDecodeForm.ts"
    fake_encode_form = tmp_path / "useEncodeForm.ts"
    fake_decode_form.write_text(
        "(currentDecoderProfile.value?.hardwareDevices ?? []).map((device) => device.toUpperCase())\n"
        "getDecoderHwaccelDeviceOptions(profile, config.hwaccel)\n"
        "resolveDecoderHwaccelDevice(profile, value)\n",
        encoding="utf-8",
    )
    fake_encode_form.write_text(
        "getRateControlModeOptions(profile)\n"
        "hasRateControlModes(profile)\n"
        "getRateControlUnit(profile, mode)\n"
        "resolveRateControlForMode(profile, mode)\n"
        "Number.isFinite(value) && value > 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_FORM_COMPOSABLES", [fake_decode_form, fake_encode_form])
    issues: list[str] = []

    module._check_frontend_io_form_rule_boundary(issues)

    assert any("io form rule" in issue for issue in issues), issues


def test_frontend_io_form_binding_boundary_flags_composable_binding_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_decode_form = tmp_path / "useDecodeForm.ts"
    fake_encode_form = tmp_path / "useEncodeForm.ts"
    fake_decode_form.write_text(
        "import { getVisibleDecoderProfiles } from '@/services/preset/profile-picker'\n"
        "import { selectDecodeProfile } from '@/services/preset/profile-selection'\n"
        "import { updateProfileOption } from '@/services/preset/options'\n",
        encoding="utf-8",
    )
    fake_encode_form.write_text(
        "import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'\n"
        "import { buildRateControlViewState } from '@/services/preset/io-form-rules'\n"
        "import { normalizeOutputDir } from '@/services/preset/normalize'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_FORM_COMPOSABLES", [fake_decode_form, fake_encode_form])
    issues: list[str] = []

    module._check_frontend_io_form_binding_boundary(issues)

    assert any("io form binding rule" in issue for issue in issues), issues


def test_frontend_io_form_aggregator_boundary_flags_rule_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_decode_bindings = tmp_path / "decode-form-bindings.ts"
    fake_encode_bindings = tmp_path / "encode-form-bindings.ts"
    fake_decode_bindings.write_text(
        "import { getVisibleDecoderProfiles } from '@/services/preset/profile-picker'\n"
        "import { selectDecodeProfile } from '@/services/preset/profile-selection'\n",
        encoding="utf-8",
    )
    fake_encode_bindings.write_text(
        "import { buildRateControlViewState } from '@/services/preset/io-form-rules'\n"
        "import { buildProfileOptions } from '@/services/preset/io-options'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_IO_FORM_BINDINGS", [fake_decode_bindings, fake_encode_bindings])
    issues: list[str] = []

    module._check_frontend_io_form_aggregator_boundary(issues)

    assert any("io form rule" in issue and "aggregator" in issue for issue in issues), issues


def test_frontend_form_binding_internal_params_are_not_exported() -> None:
    module = _load_module()
    form_dir = module.FRONTEND_SRC / "composables" / "forms"
    internal_params = {
        form_dir / "capability-option-bindings.ts": ("CapabilityOptionBindingParams",),
        form_dir / "decode-form-bindings.ts": ("DecodeFormBindingParams",),
        form_dir / "decode-hardware-bindings.ts": ("DecodeHardwareBindingParams",),
        form_dir / "decode-profile-bindings.ts": ("DecodeProfileBindingParams",),
        form_dir / "encode-form-bindings.ts": ("EncodeFormBindingParams",),
        form_dir / "encode-output-bindings.ts": ("EncodeOutputBindingParams",),
        form_dir / "encode-output-setters.ts": ("EncodeOutputSetterParams",),
        form_dir / "encode-output-state.ts": ("EncodeOutputStateParams",),
        form_dir / "encode-profile-bindings.ts": ("EncodeProfileBindingParams",),
        form_dir / "encode-rate-control-bindings.ts": ("EncodeRateControlBindingParams",),
        form_dir / "enhance-algorithm-bindings.ts": ("EnhanceAlgorithmBindingParams",),
        form_dir / "enhance-field-bindings.ts": ("EnhanceFieldBindingParams",),
        form_dir / "enhance-form-bindings.ts": ("EnhanceFormBindingParams",),
        form_dir / "enhance-scalar-field-bindings.ts": ("EnhanceScalarFieldBindingParams",),
        form_dir / "enhance-view-bindings.ts": ("EnhanceViewBindingParams",),
        form_dir / "io-profile-state.ts": ("IoProfileStateParams",),
    }

    exported = [
        f"{path.name}:{name}"
        for path, names in internal_params.items()
        for name in names
        if f"export interface {name}" in path.read_text(encoding="utf-8")
        or f"export type {name}" in path.read_text(encoding="utf-8")
    ]

    assert exported == []


def test_frontend_form_binding_param_export_boundary_flags_internal_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_binding = tmp_path / "decode-form-bindings.ts"
    fake_binding.write_text(
        "export interface DecodeFormBindingParams { patchDecode: () => void }\n"
        "export function createDecodeFormBindings(params: DecodeFormBindingParams) { return params }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_FORM_BINDING_PARAM_FILES", {fake_binding: ("DecodeFormBindingParams",)})
    issues: list[str] = []

    module._check_frontend_form_binding_param_export_boundary(issues)

    assert any("form binding params" in issue for issue in issues), issues


def test_frontend_utility_internal_types_are_not_exported() -> None:
    module = _load_module()
    frontend_src = module.FRONTEND_SRC
    internal_types = {
        frontend_src / "composables" / "forms" / "enhance-lens.ts": (
            "AlgorithmSpec",
            "AlgorithmLens",
        ),
        frontend_src / "composables" / "forms" / "useFilterChainForm.ts": ("FilterStage",),
        frontend_src / "composables" / "selectors" / "useGpuCapabilities.ts": ("GpuCapabilitiesView",),
        frontend_src / "composables" / "forms" / "enhance-option-bindings.ts": ("EnhanceOptionForm",),
        frontend_src / "lib" / "ipc" / "events.ts": ("TaskEventHandlers",),
        frontend_src / "services" / "model-runtime-estimates.ts": ("RuntimeMetricOptions",),
        frontend_src / "services" / "preset" / "io-form-rules.ts": ("RateControlViewState",),
        frontend_src / "services" / "task" / "events.ts": ("TaskLogLineKind",),
        frontend_src / "services" / "task" / "preflight.ts": (
            "BatchPreflightItem",
            "BatchPreflightInput",
            "BatchPreflightVerdict",
        ),
        frontend_src / "services" / "task" / "batch" / "conflict.ts": (
            "ConflictResolverDeps",
            "ConflictResolver",
        ),
        frontend_src / "services" / "task" / "batch" / "events.ts": (
            "EventHandlersDeps",
            "EventHandlers",
        ),
        frontend_src / "composables" / "forms" / "enhance-effect-bindings.ts": ("EnhanceEffectBindingParams",),
        frontend_src / "services" / "task" / "batch" / "lifecycle" / "common.ts": ("CommonHelpers",),
        frontend_src / "services" / "task" / "batch" / "lifecycle" / "control.ts": ("ControlOps",),
        frontend_src / "services" / "task" / "batch" / "lifecycle" / "finalize.ts": (
            "FinalizeInternalRefs",
            "FinalizeOps",
        ),
        frontend_src / "services" / "task" / "batch" / "lifecycle" / "queue.ts": (
            "QueueInternalRefs",
            "QueueOps",
        ),
    }

    exported = []
    for path, names in internal_types.items():
        text = path.read_text(encoding="utf-8")
        exported.extend(
            f"{path.name}:{name}"
            for name in names
            if f"export interface {name}" in text or f"export type {name}" in text
        )

    assert exported == []


def test_frontend_utility_internal_type_boundary_flags_internal_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_utility = tmp_path / "preflight.ts"
    fake_utility.write_text(
        "export interface BatchPreflightInput { selectedItems: unknown[] }\nexport type TaskLogLineKind = 'default'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "FRONTEND_UTILITY_INTERNAL_TYPE_FILES",
        {fake_utility: ("BatchPreflightInput", "TaskLogLineKind")},
        raising=False,
    )
    issues: list[str] = []

    module._check_frontend_utility_internal_type_boundary(issues)

    assert any("frontend utility internal type" in issue for issue in issues), issues


def test_frontend_batch_lifecycle_facade_does_not_reexport_internal_types() -> None:
    module = _load_module()
    lifecycle_index = module.FRONTEND_SRC / "services" / "task" / "batch" / "lifecycle" / "index.ts"
    text = lifecycle_index.read_text(encoding="utf-8")

    assert "export type { BatchLifecycle" not in text


def test_frontend_batch_runner_dead_boundary_matches_current_repo() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_frontend_batch_runner_dead_boundary(issues)

    assert issues == []


def test_frontend_batch_runner_dead_boundary_flags_duplicate_deps_and_unused_helper(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runner = tmp_path / "batch-runner.ts"
    fake_queue = tmp_path / "queue.ts"
    fake_runner.write_text(
        "interface BatchRunnerDeps { startTask: () => Promise<void> }\n"
        "export function createBatchRunner(deps: BatchRunnerDeps) { return deps }\n",
        encoding="utf-8",
    )
    fake_queue.write_text(
        "import type { createCommonHelpers } from './common'\n"
        "type CommonHelpers = ReturnType<typeof createCommonHelpers>\n"
        "export function createQueueOps(deps: unknown, _helpers: CommonHelpers) { return deps }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_BATCH_RUNNER", fake_runner, raising=False)
    monkeypatch.setattr(module, "FRONTEND_BATCH_QUEUE", fake_queue, raising=False)
    issues: list[str] = []

    module._check_frontend_batch_runner_dead_boundary(issues)

    assert any("BatchRunnerDeps" in issue for issue in issues), issues
    assert any("unused queue helpers" in issue for issue in issues), issues


def test_frontend_batch_runner_dead_boundary_allows_used_common_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runner = tmp_path / "batch-runner.ts"
    fake_queue = tmp_path / "queue.ts"
    fake_runner.write_text(
        "import type { BatchLifecycleDeps } from './batch/lifecycle/types'\n"
        "export function createBatchRunner(deps: BatchLifecycleDeps) { return deps }\n",
        encoding="utf-8",
    )
    fake_queue.write_text(
        "import type { createCommonHelpers } from './common'\n"
        "type CommonHelpers = ReturnType<typeof createCommonHelpers>\n"
        "export function createQueueOps(helpers: CommonHelpers) { return helpers.getCurrentItem() }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_BATCH_RUNNER", fake_runner, raising=False)
    monkeypatch.setattr(module, "FRONTEND_BATCH_QUEUE", fake_queue, raising=False)
    issues: list[str] = []

    module._check_frontend_batch_runner_dead_boundary(issues)

    assert issues == []


def test_frontend_batch_lifecycle_facade_boundary_flags_type_reexports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_index = tmp_path / "index.ts"
    fake_index.write_text(
        "export type { BatchLifecycle, BatchLifecycleDeps } from './types'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_BATCH_LIFECYCLE_INDEX", fake_index, raising=False)
    issues: list[str] = []

    module._check_frontend_batch_lifecycle_facade_boundary(issues)

    assert any("batch lifecycle facade" in issue for issue in issues), issues


def test_frontend_io_profile_state_boundary_flags_local_profile_derivation(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_decode_profile = tmp_path / "decode-profile-bindings.ts"
    fake_encode_profile = tmp_path / "encode-profile-bindings.ts"
    fake_decode_profile.write_text(
        "import { buildProfileOptions } from '@/services/preset/io-options'\n"
        "const decoderProfileOptions = computed(() => buildProfileOptions(visibleDecoderProfiles.value))\n"
        "const currentDecoderProfile = computed(() => visibleDecoderProfiles.value.find((profile) => profile.name === selected))\n"
        "const decoderOptions = computed(() => currentDecoderProfile.value?.options ?? [])\n",
        encoding="utf-8",
    )
    fake_encode_profile.write_text(
        "const currentEncoderProfile = computed(() => visibleEncoderProfiles.value.find((profile) => profile.name === selected))\n"
        "const encoderOptions = computed(() => currentEncoderProfile.value?.options ?? [])\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_IO_PROFILE_BINDINGS", [fake_decode_profile, fake_encode_profile])
    issues: list[str] = []

    module._check_frontend_io_profile_state_boundary(issues)

    assert any("io profile state rule" in issue for issue in issues), issues


def test_frontend_decode_hardware_binding_boundary_flags_profile_hardware_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_decode_profile = tmp_path / "decode-profile-bindings.ts"
    fake_decode_profile.write_text(
        "import { buildDecoderHardwareDeviceOptions, applyDecodeHwaccelSelection } from '@/services/preset/io-form-rules'\n"
        "const decoderHardwareDeviceOptions = computed(() => buildDecoderHardwareDeviceOptions(profile.value))\n"
        "function setDecodeHwaccel(value) { applyDecodeHwaccelSelection(config, profile.value, value) }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "DECODE_PROFILE_BINDINGS", fake_decode_profile)
    issues: list[str] = []

    module._check_frontend_decode_hardware_binding_boundary(issues)

    assert any("decode hardware binding rule" in issue for issue in issues), issues


def test_frontend_enhance_binding_boundary_flags_composable_binding_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_form = tmp_path / "useEnhanceForm.ts"
    fake_form.write_text(
        "import { createDraftEditor } from '@/composables/forms/lens'\n"
        "import { createAlgorithmLens } from '@/composables/forms/enhance-lens'\n"
        "import { buildEnhanceViewModel } from '@/services/preset/enhance-view-model'\n"
        "applyInterpolationEnabled(c, value, envStore.env.checkResult)\n"
        "superResolutionInputFramesLabel: '每块输入帧数'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_FORM", fake_form)
    issues: list[str] = []

    module._check_frontend_enhance_binding_boundary(issues)

    assert any("enhance binding rule" in issue for issue in issues), issues


def test_frontend_enhance_field_binding_boundary_flags_binding_rule_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_bindings = tmp_path / "enhance-form-bindings.ts"
    fake_bindings.write_text(
        "import { createDraftEditor } from '@/composables/forms/lens'\n"
        "import { applyInterpolationEnabled } from '@/services/preset/enhance-workflow'\n"
        "const interpolationEnabled = effect<boolean>(() => workflow.value.interpolation.enabled, () => {})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_FORM_BINDINGS", fake_bindings)
    issues: list[str] = []

    module._check_frontend_enhance_field_binding_boundary(issues)

    assert any("enhance field binding rule" in issue for issue in issues), issues


def test_frontend_enhance_field_split_boundary_flags_aggregator_rule_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_bindings = tmp_path / "enhance-field-bindings.ts"
    fake_bindings.write_text(
        "import { createDraftEditor } from '@/composables/forms/lens'\n"
        "import { applyInterpolationEnabled } from '@/services/preset/enhance-workflow'\n"
        "const interpolationEngine = field((c) => c.interpolation.engine, () => {})\n"
        "const interpolationEnabled = effect<boolean>(() => workflow.value.interpolation.enabled, () => {})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_FIELD_BINDINGS", fake_bindings)
    issues: list[str] = []

    module._check_frontend_enhance_field_split_boundary(issues)

    assert any("enhance field split rule" in issue for issue in issues), issues


def test_frontend_enhance_projection_boundary_flags_algorithm_and_view_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_bindings = tmp_path / "enhance-form-bindings.ts"
    fake_bindings.write_text(
        "import { createAlgorithmLens } from '@/composables/forms/enhance-lens'\n"
        "import { buildEnhanceViewModel } from '@/services/preset/enhance-view-model'\n"
        "const current = createAlgorithmLens(all, selected, backend)\n"
        "const viewModel = buildEnhanceViewModel(input)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_FORM_BINDINGS", fake_bindings)
    issues: list[str] = []

    module._check_frontend_enhance_projection_boundary(issues)

    assert any("enhance projection rule" in issue for issue in issues), issues


def test_frontend_enhance_binding_type_boundary_flags_local_video_dimensions(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_form_bindings = tmp_path / "enhance-form-bindings.ts"
    fake_view_bindings = tmp_path / "enhance-view-bindings.ts"
    fake_form_bindings.write_text("interface VideoDimensions { width: number; height: number }\n", encoding="utf-8")
    fake_view_bindings.write_text("interface VideoDimensions { width: number; height: number }\n", encoding="utf-8")
    monkeypatch.setattr(module, "ENHANCE_FORM_BINDINGS", fake_form_bindings)
    monkeypatch.setattr(module, "ENHANCE_VIEW_BINDINGS", fake_view_bindings, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_binding_type_boundary(issues)

    assert any("enhance binding type" in issue for issue in issues), issues


def test_frontend_enhance_lens_boundary_flags_inline_backend_support_check(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_lens = tmp_path / "enhance-lens.ts"
    fake_lens.write_text(
        "const algorithms = allAlgorithms.value.filter((algorithm) => algorithm.tensorBackends.includes(backend.value))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_LENS", fake_lens)
    issues: list[str] = []

    module._check_frontend_enhance_lens_boundary(issues)

    assert any("enhance lens" in issue for issue in issues), issues


def test_frontend_enhance_view_model_split_boundary_flags_local_model_and_runtime_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_view_model = tmp_path / "enhance-view-model.ts"
    fake_view_model.write_text(
        "import { estimateModelRuntimeMetrics, metricRows, resolveMetricsForEngine } from '@/services/model-metrics'\n"
        "import { fixedRuntimeFrameCount, isPaddleGanVsrAlgorithm } from './enhance-algorithm-capabilities'\n"
        "function selectedModelDetail() {}\n"
        "function scaledDimensions() {}\n"
        "const interpolationRuntimeEstimate = estimateModelRuntimeMetrics()\n"
        "const rows = metricRows()\n"
        "const current = resolveMetricsForEngine()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_VIEW_MODEL", fake_view_model, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_view_model_split_boundary(issues)

    assert any("enhance view-model split" in issue for issue in issues), issues


def test_frontend_enhance_runtime_view_split_boundary_flags_local_runtime_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime_view = tmp_path / "enhance-runtime-view.ts"
    fake_runtime_view.write_text(
        "import { estimateModelRuntimeMetrics, metricRows } from '@/services/model-metrics'\n"
        "import { fixedRuntimeFrameCount, isPaddleGanVsrAlgorithm } from './enhance-algorithm-capabilities'\n"
        "function scaledDimensions() {}\n"
        "const estimate = estimateModelRuntimeMetrics()\n"
        "const rows = metricRows()\n"
        "const frames = fixedRuntimeFrameCount()\n"
        "const isPaddle = isPaddleGanVsrAlgorithm()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_RUNTIME_VIEW", fake_runtime_view, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_runtime_view_split_boundary(issues)

    assert any("enhance runtime-view split" in issue for issue in issues), issues


def test_frontend_enhance_read_model_internal_types_are_not_exported() -> None:
    module = _load_module()
    preset_dir = module.FRONTEND_SRC / "services" / "preset"
    internal_types = {
        preset_dir / "enhance-model-selection.ts": (
            "EnhanceModelSelectionInput",
            "EnhanceModelSelection",
        ),
        preset_dir / "enhance-runtime-estimates.ts": (
            "EnhanceRuntimeEstimatesInput",
            "EnhanceRuntimeEstimates",
        ),
        preset_dir / "enhance-runtime-rows.ts": (
            "EnhanceRuntimeFrameStateInput",
            "EnhanceRuntimeFrameState",
            "EnhanceRuntimeRowsInput",
            "EnhanceRuntimeRows",
        ),
        preset_dir / "enhance-runtime-view.ts": (
            "EnhanceRuntimeViewInput",
            "EnhanceRuntimeView",
        ),
        preset_dir / "enhance-view-model.ts": (
            "EnhanceViewModelInput",
            "EnhanceViewModel",
        ),
    }
    type_reexport_files = (
        preset_dir / "enhance-runtime-estimates.ts",
        preset_dir / "enhance-runtime-rows.ts",
        preset_dir / "enhance-runtime-view.ts",
    )

    exported = []
    for path, names in internal_types.items():
        text = path.read_text(encoding="utf-8")
        exported.extend(
            f"{path.name}:{name}"
            for name in names
            if f"export interface {name}" in text or f"export type {name}" in text
        )
    exported.extend(
        f"{path.name}:type-reexport"
        for path in type_reexport_files
        if "export type {" in path.read_text(encoding="utf-8")
    )

    assert exported == []


def test_frontend_enhance_read_model_type_boundary_flags_internal_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_view_model = tmp_path / "enhance-view-model.ts"
    fake_runtime_view = tmp_path / "enhance-runtime-view.ts"
    fake_view_model.write_text(
        "export interface EnhanceViewModelInput { workflow: unknown }\n"
        "export interface EnhanceViewModel { rows: unknown[] }\n",
        encoding="utf-8",
    )
    fake_runtime_view.write_text(
        "export type { MetricRow, RuntimeMetricEstimate, VideoDimensions }\n"
        "export interface EnhanceRuntimeViewInput { workflow: unknown }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "FRONTEND_ENHANCE_READ_MODEL_INTERNAL_TYPE_FILES",
        {
            fake_view_model: ("EnhanceViewModelInput", "EnhanceViewModel"),
            fake_runtime_view: ("EnhanceRuntimeViewInput", "EnhanceRuntimeView"),
        },
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "FRONTEND_ENHANCE_READ_MODEL_TYPE_REEXPORT_FILES",
        (fake_runtime_view,),
        raising=False,
    )
    issues: list[str] = []

    module._check_frontend_enhance_read_model_type_boundary(issues)

    assert any("enhance read-model type" in issue for issue in issues), issues


def test_frontend_model_metrics_barrel_boundary_flags_local_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_model_metrics = tmp_path / "model-metrics.ts"
    fake_model_metrics.write_text(
        "export function formatBytes() { return '--' }\n"
        "export function resolveMetricsForEngine() { return null }\n"
        "export function estimateModelRuntimeMetrics() { return null }\n"
        "export function metricRows() { return [] }\n"
        "const UNKNOWN = '--'\n"
        "function finiteOrNull() { return null }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "MODEL_METRICS", fake_model_metrics, raising=False)
    issues: list[str] = []

    module._check_frontend_model_metrics_barrel_boundary(issues)

    assert any("model metrics barrel" in issue for issue in issues), issues


def test_frontend_model_metrics_barrel_boundary_flags_obsolete_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_model_metrics = tmp_path / "model-metrics.ts"
    fake_model_metrics.write_text(
        "export { formatBytes, modelOptionLabel } from './model-metric-format'\n"
        "export { resolveMetricsForEngine } from './model-engine-metrics'\n"
        "export { estimateModelRuntimeMetrics } from './model-runtime-estimates'\n"
        "export type { RuntimeMetricEstimate } from './model-runtime-estimates'\n"
        "export { metricRows } from './model-metric-rows'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "MODEL_METRICS", fake_model_metrics, raising=False)
    issues: list[str] = []

    module._check_frontend_model_metrics_barrel_boundary(issues)

    assert any("obsolete model metrics barrel" in issue for issue in issues), issues


def test_frontend_model_metrics_barrel_boundary_allows_missing_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_model_metrics = tmp_path / "missing-model-metrics.ts"
    monkeypatch.setattr(module, "MODEL_METRICS", fake_model_metrics, raising=False)
    issues: list[str] = []

    module._check_frontend_model_metrics_barrel_boundary(issues)

    assert issues == []


def test_frontend_model_metric_view_type_boundary_flags_service_type_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "model-runtime-estimates.ts"
    fake_rows = tmp_path / "model-metric-rows.ts"
    fake_runtime.write_text(
        "export interface VideoDimensions {}\nexport interface RuntimeMetricEstimate {}\n",
        encoding="utf-8",
    )
    fake_rows.write_text("export interface MetricRow {}\n", encoding="utf-8")
    monkeypatch.setattr(module, "MODEL_RUNTIME_ESTIMATES", fake_runtime, raising=False)
    monkeypatch.setattr(module, "MODEL_METRIC_ROWS", fake_rows, raising=False)
    issues: list[str] = []

    module._check_frontend_model_metric_view_type_boundary(issues)

    assert any("model metric view type" in issue for issue in issues), issues


def test_frontend_preset_clone_boundary_flags_generic_clone_export(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_clone = tmp_path / "clone.ts"
    fake_clone.write_text(
        "export function clone<T>(value: T): T { return value }\n"
        "export const cloneWorkflowConfig = (config) => clone(config)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PRESET_CLONE", fake_clone, raising=False)
    issues: list[str] = []

    module._check_frontend_preset_clone_boundary(issues)

    assert any("preset clone surface" in issue for issue in issues), issues


def test_frontend_format_numbers_boundary_flags_obsolete_single_use_helper(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_numbers = tmp_path / "numbers.ts"
    fake_numbers.write_text(
        "export function formatNumber(value: number): string { return `${value}` }\n", encoding="utf-8"
    )
    monkeypatch.setattr(module, "FRONTEND_FORMAT_NUMBERS", fake_numbers, raising=False)
    issues: list[str] = []

    module._check_frontend_format_numbers_boundary(issues)

    assert any("obsolete format numbers helper" in issue for issue in issues), issues


def test_frontend_domain_preset_barrel_boundary_flags_obsolete_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_domain_preset = tmp_path / "preset.ts"
    fake_domain_preset.write_text(
        "export type { WorkbenchPreset, DecodeConfig } from '../protocol'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "DOMAIN_PRESET_TYPES", fake_domain_preset, raising=False)
    issues: list[str] = []

    module._check_frontend_domain_preset_barrel_boundary(issues)

    assert any("obsolete domain preset type barrel" in issue for issue in issues), issues


def test_frontend_ipc_barrel_boundary_flags_obsolete_barrel_and_root_import(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_ipc_barrel = tmp_path / "index.ts"
    fake_source_root = tmp_path / "src"
    fake_source_root.mkdir()
    fake_ipc_barrel.write_text("export { safeInvoke } from './client'\n", encoding="utf-8")
    (fake_source_root / "consumer.ts").write_text(
        "import type { UnlistenFn } from '@/lib/ipc'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FRONTEND_IPC_INDEX", fake_ipc_barrel, raising=False)
    monkeypatch.setattr(module, "FRONTEND_SRC", fake_source_root, raising=False)
    issues: list[str] = []

    module._check_frontend_ipc_barrel_boundary(issues)

    assert any("obsolete IPC barrel" in issue for issue in issues), issues
    assert any("obsolete IPC barrel import" in issue for issue in issues), issues


def test_frontend_task_orchestrator_runtime_boundary_flags_runtime_reexports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_orchestrator = tmp_path / "useTaskOrchestrator.ts"
    fake_orchestrator.write_text(
        "export { disposeRunner } from './taskOrchestratorRuntime'\nexport * from './taskOrchestratorRuntime'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "USE_TASK_ORCHESTRATOR", fake_orchestrator, raising=False)
    issues: list[str] = []

    module._check_frontend_task_orchestrator_runtime_boundary(issues)

    assert any("runtime dispose re-export" in issue for issue in issues), issues
    assert any("runtime wildcard re-export" in issue for issue in issues), issues


def test_planning_test_private_alias_boundary_flags_legacy_resolve_aliases(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_tests = tmp_path / "tests"
    fake_tests.mkdir()
    (fake_tests / "test_cli.py").write_text(
        "from app.planning import (\n"
        "    resolve_expected_output_frames as _resolve_expected_output_frames,\n"
        "    resolve_processing_steps as _resolve_processing_steps,\n"
        ")\n\n"
        "def test_steps():\n"
        "    _resolve_processing_steps({})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BACKEND_TESTS", fake_tests, raising=False)
    issues: list[str] = []

    module._check_planning_test_private_alias_boundary(issues)

    assert any("planning test private alias" in issue for issue in issues), issues


def test_planning_test_private_alias_boundary_flags_single_line_resolve_alias(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_tests = tmp_path / "tests"
    fake_tests.mkdir()
    (fake_tests / "test_cli_resolve_steps.py").write_text(
        "from app.planning import resolve_processing_steps as _resolve_processing_steps\n\n"
        "def test_steps():\n"
        "    _resolve_processing_steps({})\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BACKEND_TESTS", fake_tests, raising=False)
    issues: list[str] = []

    module._check_planning_test_private_alias_boundary(issues)

    assert any("planning test private alias" in issue for issue in issues), issues


def test_pipeline_test_private_alias_boundary_flags_output_dimension_alias(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_tests = tmp_path / "test_processing"
    fake_tests.mkdir()
    (fake_tests / "test_paddlegan_output_dimensions.py").write_text(
        "from app.processing.streaming.pipeline import _resolved_output_dimensions\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR_TESTS", fake_tests, raising=False)
    issues: list[str] = []

    module._check_pipeline_test_private_alias_boundary(issues)

    assert any("pipeline test private alias" in issue for issue in issues), issues


def test_cli_process_planning_validation_boundary_flags_local_validation_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_planning = tmp_path / "_process_planning.py"
    fake_planning.write_text(
        "def _get_onnx_model_name(config):\n"
        "    return config.get('onnxModel')\n\n"
        "def _validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name):\n"
        "    pass\n\n"
        "def _verify_model_availability(workflow_config, processing_steps, tensor_backend_name):\n"
        "    pass\n\n"
        "def _verify_super_resolution_backend(workflow_config, tensor_backend_name):\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CLI_PROCESS_PLANNING", fake_planning, raising=False)
    issues: list[str] = []

    module._check_cli_process_planning_validation_boundary(issues)

    assert any("CLI process planning validation" in issue for issue in issues), issues


def test_cli_process_planning_validation_boundary_flags_private_validation_reexports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_planning = tmp_path / "_process_planning.py"
    fake_planning.write_text(
        "from app.planning import verify_model_availability as _verify_model_availability\n"
        "from app.planning import verify_super_resolution_backend as _verify_super_resolution_backend\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CLI_PROCESS_PLANNING", fake_planning, raising=False)
    issues: list[str] = []

    module._check_cli_process_planning_validation_boundary(issues)

    assert any("private validation re-export" in issue for issue in issues), issues


def test_planning_state_boundary_matches_current_repo() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_planning_state_boundary(issues)

    assert issues == []


def test_planning_state_boundary_flags_redundant_fields(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_plan = tmp_path / "stage_plan.py"
    fake_process_planning = tmp_path / "_process_planning.py"
    fake_stage_plan.write_text(
        "class StagePlan:\n    total_output_frames: int\n    total_pairs: int\n",
        encoding="utf-8",
    )
    fake_process_planning.write_text(
        "class ProcessingPlan:\n    output_dir: str\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_PLAN", fake_stage_plan, raising=False)
    monkeypatch.setattr(module, "CLI_PROCESS_PLANNING", fake_process_planning)
    issues: list[str] = []

    module._check_planning_state_boundary(issues)

    assert any("total_output_frames" in issue for issue in issues), issues
    assert any("total_pairs" in issue for issue in issues), issues
    assert any("output_dir" in issue for issue in issues), issues


def test_obsolete_tensor_chain_boundary_flags_helper_and_tests(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_helper = tmp_path / "_tensor_chain.py"
    fake_test = tmp_path / "test_tensor_chain.py"
    fake_helper.write_text("def run_tensor_chain():\n    pass\n", encoding="utf-8")
    fake_test.write_text(
        "from app.processing.streaming._tensor_chain import run_tensor_chain\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "TENSOR_CHAIN", fake_helper, raising=False)
    monkeypatch.setattr(module, "TENSOR_CHAIN_TEST", fake_test, raising=False)
    issues: list[str] = []

    module._check_obsolete_tensor_chain_boundary(issues)

    assert any("obsolete tensor chain helper" in issue for issue in issues), issues
    assert any("obsolete tensor chain test" in issue for issue in issues), issues


def test_obsolete_in_process_streaming_workers_boundary_flags_files_tests_and_references(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_worker = tmp_path / "processor.py"
    fake_test = tmp_path / "test_processor_streams.py"
    fake_doc = tmp_path / "backend-architecture.md"
    fake_worker.write_text("def _processor_worker():\n    pass\n", encoding="utf-8")
    fake_test.write_text(
        "from app.processing.streaming.processor_algorithms import PipelineAlgorithms\n",
        encoding="utf-8",
    )
    fake_doc.write_text(
        "[processor.py](../backend/app/processing/streaming/processor.py)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "OBSOLETE_IN_PROCESS_STREAMING_FILES", (fake_worker,), raising=False)
    monkeypatch.setattr(module, "OBSOLETE_IN_PROCESS_STREAMING_TESTS", (fake_test,), raising=False)
    monkeypatch.setattr(module, "OBSOLETE_IN_PROCESS_STREAMING_REFERENCE_ROOTS", (fake_doc,), raising=False)
    issues: list[str] = []

    module._check_obsolete_in_process_streaming_workers_boundary(issues)

    assert any("obsolete in-process streaming worker" in issue for issue in issues), issues
    assert any("obsolete in-process streaming worker test" in issue for issue in issues), issues
    assert any("obsolete in-process streaming worker reference" in issue for issue in issues), issues


def test_obsolete_in_process_streaming_workers_boundary_flags_stale_metrics_runtime_text(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_doc = tmp_path / "metrics.py"
    fake_doc.write_text(
        "specific接入到 ``_run_streaming_pipeline``\nDesigned for the three-worker producer/consumer model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "OBSOLETE_IN_PROCESS_STREAMING_FILES", (), raising=False)
    monkeypatch.setattr(module, "OBSOLETE_IN_PROCESS_STREAMING_TESTS", (), raising=False)
    monkeypatch.setattr(module, "OBSOLETE_IN_PROCESS_STREAMING_REFERENCE_ROOTS", (fake_doc,), raising=False)
    issues: list[str] = []

    module._check_obsolete_in_process_streaming_workers_boundary(issues)

    assert any("obsolete in-process streaming worker reference" in issue for issue in issues), issues


def test_obsolete_decode_queue_boundary_flags_queue_worker_and_doc_references(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_queues = tmp_path / "queues.py"
    fake_encoder_worker = tmp_path / "encoder_worker.py"
    fake_raw_encoder = tmp_path / "pipeline_raw_encoder.py"
    fake_doc = tmp_path / "data-flow.md"
    fake_queues.write_text("class DecodedFrame:\n    pass\n\n_DECODE_END = object()\n", encoding="utf-8")
    fake_encoder_worker.write_text("def run_encoder_worker(decode_queue, encode_queue):\n    pass\n", encoding="utf-8")
    fake_raw_encoder.write_text('"decode_queue": queue.Queue(maxsize=1)\n', encoding="utf-8")
    fake_doc.write_text("decoder_worker -> processor_worker -> encoder_worker\nDecodedFrame\n", encoding="utf-8")
    monkeypatch.setattr(module, "STREAMING_QUEUES", fake_queues, raising=False)
    monkeypatch.setattr(module, "ENCODER_WORKER", fake_encoder_worker, raising=False)
    monkeypatch.setattr(module, "PIPELINE_RAW_ENCODER", fake_raw_encoder, raising=False)
    monkeypatch.setattr(module, "OBSOLETE_DECODE_QUEUE_REFERENCE_ROOTS", (fake_doc,), raising=False)
    issues: list[str] = []

    module._check_obsolete_decode_queue_boundary(issues)

    assert any("obsolete decode queue symbol" in issue for issue in issues), issues
    assert any("obsolete decode queue parameter" in issue for issue in issues), issues
    assert any("obsolete decode queue wiring" in issue for issue in issues), issues
    assert any("obsolete decode queue reference" in issue for issue in issues), issues


def test_stage_file_pipeline_chunk_boundary_flags_local_chunk_and_rule_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "stage_file_pipeline.py"
    fake_pipeline.write_text(
        "from app.planning import SegmentManifest\n"
        "from app.processing.streaming.stage_file_rules import safe_stage_name, stage_signature\n\n"
        "def _run_single_stage_file_chunks():\n"
        "    pass\n\n"
        "def _run_stage_chunk_to_file():\n"
        "    pass\n\n"
        "def _chunk_progress_adapter():\n"
        "    pass\n\n"
        "def _stage_signature():\n"
        "    pass\n\n"
        "def _safe_stage_name():\n"
        "    pass\n\n"
        "def run_stage_file_pipeline(step):\n"
        "    SegmentManifest('stage.mp4')\n"
        "    stage_signature(1, step, 'input.mp4', 'stage.mp4')\n"
        "    safe_stage_name(step)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_stage_file_pipeline_chunk_boundary(issues)

    assert any("stage file chunk rule" in issue for issue in issues), issues
    assert any("direct stage-file rule import" in issue for issue in issues), issues
    assert any("intermediate manifest construction" in issue for issue in issues), issues
    assert any("direct intermediate stage signature" in issue for issue in issues), issues
    assert any("direct safe stage name" in issue for issue in issues), issues


def test_stage_file_chunks_runtime_boundary_flags_local_runtime_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_chunks = tmp_path / "stage_file_chunks.py"
    fake_chunks.write_text(
        "import queue\n"
        "import tempfile\n"
        "import threading\n"
        "from app.processing.streaming.stage_worker import StageWorkerConfig, read_rgb_frame\n"
        "from app.processing.streaming.worker_processes import spawn_stage_workers, write_decoded_frames_to_worker\n\n"
        "def run_stage_chunk_to_file():\n"
        "    pass\n\n"
        "def chunk_progress_adapter():\n"
        "    pass\n\n"
        "def stage_chunk_output_start():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNKS", fake_chunks)
    issues: list[str] = []

    module._check_stage_file_chunks_runtime_boundary(issues)

    assert any("stage file chunk runtime" in issue for issue in issues), issues


def test_stage_file_chunks_runtime_boundary_flags_compatibility_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_chunks = tmp_path / "stage_file_chunks.py"
    fake_chunks.write_text(
        "from app.processing.streaming.stage_file_chunk_progress import (\n"
        "    chunk_progress_adapter,\n"
        "    stage_chunk_output_start,\n"
        ")\n"
        "from app.processing.streaming.stage_file_chunk_runtime import run_stage_chunk_to_file\n\n"
        "from app.processing.streaming.stage_file_chunk_runtime import run_stage_chunk_to_file as _run_stage_chunk_to_file\n\n"
        "def run_single_stage_file_chunks():\n"
        "    _run_stage_chunk_to_file()\n\n"
        "__all__ = [\n"
        '    "chunk_progress_adapter",\n'
        '    "run_single_stage_file_chunks",\n'
        '    "run_stage_chunk_to_file",\n'
        '    "stage_chunk_output_start",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNKS", fake_chunks)
    issues: list[str] = []

    module._check_stage_file_chunks_runtime_boundary(issues)

    assert any("public chunk runtime import" in issue for issue in issues), issues
    assert any("private chunk runtime alias import" in issue for issue in issues), issues
    assert any("private chunk runtime alias call" in issue for issue in issues), issues
    assert any("progress helper import" in issue for issue in issues), issues
    assert any("helper __all__ export" in issue for issue in issues), issues


def test_stage_file_chunk_input_fps_boundary_flags_dead_input_fps_forwarding(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_chunks = tmp_path / "stage_file_chunks.py"
    fake_pipeline = tmp_path / "stage_file_pipeline.py"
    fake_chunks.write_text(
        "def run_single_stage_file_chunks(*, input_fps: float, output_fps: float):\n"
        "    del input_fps\n"
        "    return output_fps\n",
        encoding="utf-8",
    )
    fake_pipeline.write_text(
        "def run_stage_file_pipeline(current_fps):\n"
        "    return run_single_stage_file_chunks(input_fps=current_fps, output_fps=current_fps)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNKS", fake_chunks, raising=False)
    monkeypatch.setattr(module, "STAGE_FILE_PIPELINE", fake_pipeline, raising=False)
    issues: list[str] = []

    module._check_stage_file_chunk_input_fps_boundary(issues)

    assert any("stage file chunk input_fps" in issue for issue in issues), issues


def test_stage_file_chunk_progress_boundary_flags_explicit_progress_total_discard(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_progress = tmp_path / "stage_file_chunk_progress.py"
    fake_progress.write_text(
        "def chunk_progress_adapter():\n"
        "    def adapter(current, progress_total):\n"
        "        del progress_total\n"
        "        return current\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_PROGRESS", fake_progress, raising=False)
    issues: list[str] = []

    module._check_stage_file_chunk_progress_boundary(issues)

    assert any("stage file chunk progress" in issue for issue in issues), issues


def test_stage_file_chunk_progress_boundary_flags_named_ignored_progress_total(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_progress = tmp_path / "stage_file_chunk_progress.py"
    fake_progress.write_text(
        "def chunk_progress_adapter():\n    def adapter(current, _progress_total, **kwargs):\n        return current\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_PROGRESS", fake_progress, raising=False)
    issues: list[str] = []

    module._check_stage_file_chunk_progress_boundary(issues)

    assert any("stage file chunk progress" in issue for issue in issues), issues


def test_stage_file_chunks_test_boundary_flags_stage_file_rule_tests(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_test = tmp_path / "test_stage_file_chunks.py"
    fake_test.write_text(
        "from app.processing.streaming import stage_file_rules\n\n"
        "def test_stage_file_rules_build_safe_signature():\n"
        "    stage_file_rules.stage_signature(1, step, 'input.mp4', 'stage.mp4')\n"
        "    stage_file_rules.safe_stage_name(step)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNKS_TEST", fake_test, raising=False)
    issues: list[str] = []

    module._check_stage_file_chunks_test_boundary(issues)

    assert any("stage file chunks test boundary" in issue for issue in issues), issues


def test_stage_file_pipeline_test_boundary_flags_chunk_runtime_tests(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_test = tmp_path / "test_stage_file_pipeline.py"
    fake_test.write_text(
        "import app.processing.streaming.stage_file_chunk_runtime as stage_file_chunk_runtime\n\n"
        "def test_stage_file_pipeline_runs_each_stage_as_bounded_segments():\n"
        "    stage_file_chunk_runtime.run_stage_chunk_to_file()\n"
        "    chunk.input_start_frame\n"
        "    chunk.written_output_frame_count\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_PIPELINE_TEST", fake_test, raising=False)
    issues: list[str] = []

    module._check_stage_file_pipeline_test_boundary(issues)

    assert any("stage file pipeline test boundary" in issue for issue in issues), issues


def test_stage_file_chunk_runtime_encoding_boundary_flags_local_encoding_loop(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "stage_file_chunk_runtime.py"
    fake_runtime.write_text(
        "from app.processing.streaming.encoder_segments import resolve_segment_output_frame_count\n"
        "from app.processing.streaming.stage_worker import read_rgb_frame\n\n"
        "def run_stage_chunk_to_file(ffmpeg, handle, chunk):\n"
        "    writer = ffmpeg.open_rawvideo_encoder(output_path='chunk.mp4')\n"
        "    written_frames = 0\n"
        "    for raw_index in range(chunk.raw_output_frame_count):\n"
        "        frame = read_rgb_frame(handle.process.stdout, width=1, height=1)\n"
        "        writer.write_frame(frame)\n"
        "        written_frames += 1\n"
        "    resolve_segment_output_frame_count(ffmpeg, writer, 'chunk.mp4', fallback_frame_count=written_frames)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_stage_file_chunk_runtime_encoding_boundary(issues)

    assert any("stage file chunk encoding" in issue for issue in issues), issues


def test_stage_file_chunk_runtime_encoding_boundary_flags_noop_progress_placeholders(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "stage_file_chunk_runtime.py"
    fake_runtime.write_text(
        "def run_stage_chunk_to_file(stage_total):\n"
        "    return [(lambda *_args, **_kwargs: None) for _ in range(stage_total)]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_stage_file_chunk_runtime_encoding_boundary(issues)

    assert any("stage file chunk progress placeholders" in issue for issue in issues), issues


def test_stage_worker_runtime_boundary_flags_local_io_and_runtime_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker = tmp_path / "stage_worker.py"
    fake_stage_worker.write_text(
        "class RawVideoFrameError(RuntimeError):\n"
        "    pass\n\n"
        "def read_rgb_frame():\n"
        "    pass\n\n"
        "def emit_stage_event():\n"
        "    pass\n\n"
        "def _create_algorithm():\n"
        "    pass\n\n"
        "class _StageProgressState:\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER", fake_stage_worker)
    issues: list[str] = []

    module._check_stage_worker_runtime_boundary(issues)

    assert any("stage worker runtime rule" in issue for issue in issues), issues


def test_stage_worker_entrypoint_export_boundary_flags_compatibility_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker = tmp_path / "stage_worker.py"
    fake_stage_worker.write_text(
        "from app.processing.streaming.stage_worker_config import StageWorkerConfig\n"
        "from app.processing.streaming.stage_worker_io import (\n"
        "    RawVideoFrameError,\n"
        "    read_rgb_frame,\n"
        "    write_rgb_frame,\n"
        ")\n"
        "from app.processing.streaming.stage_worker_progress import (\n"
        "    STAGE_EVENT_PREFIX,\n"
        "    emit_stage_event,\n"
        ")\n"
        "from app.processing.streaming.stage_worker_factory import (\n"
        "    AlgorithmFactory,\n"
        "    create_algorithm,\n"
        ")\n\n"
        "__all__ = [\n"
        '    "AlgorithmFactory",\n'
        '    "RawVideoFrameError",\n'
        '    "STAGE_EVENT_PREFIX",\n'
        '    "StageWorkerConfig",\n'
        '    "emit_stage_event",\n'
        '    "read_rgb_frame",\n'
        '    "run_stage_worker_stream",\n'
        '    "write_rgb_frame",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER", fake_stage_worker)
    issues: list[str] = []

    module._check_stage_worker_entrypoint_export_boundary(issues)

    assert any("rawvideo io import" in issue for issue in issues), issues
    assert any("progress helper import" in issue for issue in issues), issues
    assert any("config re-export import" in issue for issue in issues), issues
    assert any("algorithm factory re-export import" in issue for issue in issues), issues
    assert any("helper __all__ export" in issue for issue in issues), issues


def test_stage_worker_factory_public_boundary_flags_implementation_details(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_factory = tmp_path / "stage_worker_factory.py"
    fake_factory.write_text(
        "from app.algorithms.factory import AlgorithmFactory\n\n"
        "AlgorithmFactoryFn = object\n"
        "BackendFactoryFn = object\n\n"
        "def backend_name():\n"
        "    pass\n\n"
        "__all__ = [\n"
        '    "AlgorithmFactory",\n'
        '    "AlgorithmFactoryFn",\n'
        '    "BackendFactoryFn",\n'
        '    "backend_name",\n'
        '    "create_algorithm",\n'
        '    "create_backend",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER_FACTORY", fake_factory, raising=False)
    issues: list[str] = []

    module._check_stage_worker_factory_public_boundary(issues)

    assert any("stage worker factory public surface" in issue for issue in issues), issues


def test_stage_runtime_rule_helper_boundary_flags_rule_reexports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_runtime = tmp_path / "stage_runtime.py"
    fake_stage_runtime.write_text(
        "from app.processing.streaming.stage_rules import algorithm_kwargs_for_create\n\n"
        "def get_cached_backend(cache, backend_name):\n"
        "    return cache[backend_name]\n\n"
        "def entry_needs_sequence(entry):\n"
        "    return entry.algorithm.needs_frame_sequence()\n\n"
        "def should_prefer_tensor_stage(*, entry, payload, remaining, has_tensor_stage_after_chain):\n"
        "    return True\n\n"
        "__all__ = [\n"
        '    "StepAlgorithm",\n'
        '    "algorithm_kwargs_for_create",\n'
        '    "get_cached_backend",\n'
        '    "entry_needs_sequence",\n'
        '    "should_prefer_tensor_stage",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_RUNTIME", fake_stage_runtime, raising=False)
    issues: list[str] = []

    module._check_stage_runtime_rule_helper_boundary(issues)

    assert any("stage runtime rule helper" in issue for issue in issues), issues
    assert any("get_cached_backend" in issue for issue in issues), issues
    assert any("entry_needs_sequence" in issue for issue in issues), issues
    assert any("should_prefer_tensor_stage" in issue for issue in issues), issues


def test_stage_file_stage_context_surface_boundary_flags_dataclass_export(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_context = tmp_path / "stage_file_stage_context.py"
    fake_stage_context.write_text(
        "class StageFileStageContext:\n"
        "    pass\n\n"
        "def build_stage_file_stage_context():\n"
        "    return StageFileStageContext()\n\n"
        '__all__ = ["StageFileStageContext", "build_stage_file_stage_context"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_STAGE_CONTEXT", fake_stage_context, raising=False)
    issues: list[str] = []

    module._check_stage_file_stage_context_surface_boundary(issues)

    assert any("StageFileStageContext" in issue for issue in issues), issues


def test_stage_worker_io_surface_boundary_flags_declared_frame_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker_io = tmp_path / "stage_worker_io.py"
    fake_stage_worker_io.write_text(
        "def read_declared_frames():\n"
        "    pass\n\n"
        "__all__ = [\n"
        '    "RawVideoFrameError",\n'
        '    "read_declared_frames",\n'
        '    "read_rgb_frame",\n'
        '    "write_rgb_frame",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER_IO", fake_stage_worker_io, raising=False)
    issues: list[str] = []

    module._check_stage_worker_io_surface_boundary(issues)

    assert any("stage worker io surface" in issue for issue in issues), issues


def test_stage_worker_helper_import_boundary_flags_helper_imports_from_entrypoint(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_encoding = tmp_path / "stage_file_chunk_encoding.py"
    fake_events = tmp_path / "worker_process_events.py"
    fake_io = tmp_path / "worker_process_io.py"
    fake_encoding.write_text(
        "from app.processing.streaming.stage_worker import read_rgb_frame\n",
        encoding="utf-8",
    )
    fake_events.write_text(
        "from app.processing.streaming.stage_worker import STAGE_EVENT_PREFIX, emit_stage_event\n",
        encoding="utf-8",
    )
    fake_io.write_text(
        "from app.processing.streaming.stage_worker import RawVideoFrameError, read_rgb_frame, write_rgb_frame\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_ENCODING", fake_encoding, raising=False)
    monkeypatch.setattr(module, "WORKER_PROCESS_EVENTS", fake_events, raising=False)
    monkeypatch.setattr(module, "WORKER_PROCESS_IO", fake_io, raising=False)
    issues: list[str] = []

    module._check_stage_worker_helper_import_boundary(issues)

    assert any("stage worker helper" in issue for issue in issues), issues


def test_stage_worker_runtime_split_boundary_flags_local_factory_and_progress_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "stage_worker_runtime.py"
    fake_runtime.write_text(
        "from dataclasses import dataclass\n"
        "import json\n"
        "import sys\n"
        "import threading\n"
        "from app.algorithms.factory import AlgorithmFactory\n"
        "from app.processing.streaming.stage_rules import algorithm_kwargs_for_create\n\n"
        "class StageProgressState:\n"
        "    pass\n\n"
        "def emit_stage_event():\n"
        "    pass\n\n"
        "def create_backend():\n"
        "    pass\n\n"
        "def create_algorithm():\n"
        "    pass\n\n"
        "def register_single_algorithm():\n"
        "    pass\n\n"
        "def backend_name():\n"
        "    pass\n\n"
        "def progress_event():\n"
        "    pass\n\n"
        "def start_sequence_stage_heartbeat():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_stage_worker_runtime_split_boundary(issues)

    assert any("stage worker runtime split" in issue for issue in issues), issues


def test_stage_worker_runtime_split_boundary_flags_obsolete_runtime_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "stage_worker_runtime.py"
    fake_runtime.write_text(
        '"""Compatibility barrel for isolated stage worker runtime helpers."""\n\n'
        "from app.processing.streaming.stage_worker_factory import create_backend\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_stage_worker_runtime_split_boundary(issues)

    assert any("obsolete stage worker runtime barrel" in issue for issue in issues), issues


def test_stage_worker_runtime_test_boundary_flags_obsolete_test_file(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime_test = tmp_path / "test_stage_worker_runtime.py"
    fake_runtime_test.write_text("def test_legacy_runtime_surface():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(module, "STAGE_WORKER_RUNTIME_TEST", fake_runtime_test, raising=False)
    issues: list[str] = []

    module._check_stage_worker_runtime_test_boundary(issues)

    assert any("obsolete stage worker runtime test" in issue for issue in issues), issues


def test_stage_worker_entrypoint_test_boundary_flags_split_helper_tests(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker_test = tmp_path / "test_stage_worker.py"
    fake_stage_worker_test.write_text(
        "from app.processing.streaming.stage_worker_config import StageWorkerConfig\n"
        "from app.processing.streaming.stage_worker_io import RawVideoFrameError, read_rgb_frame\n\n"
        "def test_stage_worker_config_accepts_jsonable_stage_shape():\n"
        "    return StageWorkerConfig.from_mapping({})\n\n"
        "def test_read_rgb_frame_rejects_partial_frame():\n"
        "    return read_rgb_frame(None, width=1, height=1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER_TEST", fake_stage_worker_test, raising=False)
    issues: list[str] = []

    module._check_stage_worker_entrypoint_test_boundary(issues)

    assert any("stage worker entrypoint test boundary" in issue for issue in issues), issues


def test_stage_worker_execution_boundary_flags_local_stage_loops(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker = tmp_path / "stage_worker.py"
    fake_stage_worker.write_text(
        "def _run_sequence_stage():\n"
        "    pass\n\n"
        "def _run_interpolation_stage():\n"
        "    pass\n\n"
        "def _run_single_frame_stage():\n"
        "    pass\n\n"
        "_run_sequence_stage = run_sequence_stage\n"
        "_run_interpolation_stage = run_interpolation_stage\n"
        "_run_single_frame_stage = run_single_frame_stage\n\n"
        "def run_stage_worker_stream():\n"
        "    _run_sequence_stage()\n"
        "    _run_interpolation_stage()\n"
        "    _run_single_frame_stage()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER", fake_stage_worker)
    issues: list[str] = []

    module._check_stage_worker_execution_boundary(issues)

    assert any("stage worker execution rule" in issue for issue in issues), issues
    assert any("stage execution alias assignment" in issue for issue in issues), issues
    assert any("stage execution alias call" in issue for issue in issues), issues


def test_stage_worker_sequence_metrics_boundary_flags_dead_metrics_forwarding(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_execution = tmp_path / "stage_worker_execution.py"
    fake_worker = tmp_path / "stage_worker.py"
    fake_execution.write_text(
        "def run_sequence_stage(config, metrics):\n    del metrics\n    return 0\n",
        encoding="utf-8",
    )
    fake_worker.write_text(
        "def run_stage_worker_stream(config, metrics):\n    return run_sequence_stage(config, metrics)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER_EXECUTION", fake_execution, raising=False)
    monkeypatch.setattr(module, "STAGE_WORKER", fake_worker, raising=False)
    issues: list[str] = []

    module._check_stage_worker_sequence_metrics_boundary(issues)

    assert any("stage worker sequence metrics" in issue for issue in issues), issues


def test_stage_worker_config_boundary_flags_local_config_model(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker = tmp_path / "stage_worker.py"
    fake_stage_worker.write_text(
        "import json\n"
        "from app.planning import normalize_processing_step\n\n"
        "class StageWorkerConfig:\n"
        "    def from_mapping(self):\n"
        "        normalize_processing_step({})\n"
        "    def from_json_file(self):\n"
        "        json.load(open('config.json'))\n"
        "    def to_jsonable(self):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER", fake_stage_worker)
    issues: list[str] = []

    module._check_stage_worker_config_boundary(issues)

    assert any("stage worker config" in issue for issue in issues), issues


def test_streaming_pipeline_rule_boundary_flags_local_pipeline_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_pipeline.write_text(
        "def _build_config_snapshot():\n"
        "    pass\n\n"
        "def _should_use_stage_file_pipeline():\n"
        "    pass\n\n"
        "def _resolved_output_dimensions():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_streaming_pipeline_rule_boundary(issues)

    assert any("streaming pipeline rule" in issue for issue in issues), issues


def test_streaming_pipeline_raw_boundary_flags_local_runtime_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_pipeline.write_text(
        "import queue\n"
        "import threading\n"
        "from app.processing.streaming.encoder import _encoder_worker\n\n"
        "def _run_streaming_pipeline():\n"
        "    encode_queue = queue.Queue(maxsize=8)\n"
        "    error_queue = queue.Queue()\n"
        "    stop_event = threading.Event()\n"
        "    encoder_thread = threading.Thread(target=_encoder_worker)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_streaming_pipeline_raw_boundary(issues)

    assert any("raw pipeline runtime" in issue for issue in issues), issues


def test_pipeline_raw_runtime_boundary_flags_local_queue_thread_runtime(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline_raw = tmp_path / "pipeline_raw.py"
    fake_pipeline_raw.write_text(
        "import queue\n"
        "import threading\n"
        "from app.processing.streaming.encoder import _encoder_worker\n\n"
        "def run_raw_streaming_pipeline():\n"
        "    encode_queue = queue.Queue(maxsize=8)\n"
        "    error_queue = queue.Queue()\n"
        "    stop_event = threading.Event()\n"
        "    encoder_thread = threading.Thread(target=_encoder_worker)\n"
        "    encoder_thread.start()\n"
        "    stage_worker_runner(encode_queue=encode_queue, error_queue=error_queue, stop_event=stop_event)\n"
        "    encoder_thread.join()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW", fake_pipeline_raw, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_boundary(issues)

    assert any("pipeline raw runtime" in issue for issue in issues), issues


def test_pipeline_raw_runtime_boundary_flags_worker_chain_coupling(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline_raw = tmp_path / "pipeline_raw.py"
    fake_pipeline_raw.write_text(
        "from app.processing.streaming.pipeline_raw_stage import StageWorkerRunner\n"
        "from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline\n\n"
        "def run_raw_streaming_pipeline(stage_worker_runner=None):\n"
        "    return run_raw_pipeline_runtime(stage_worker_runner=stage_worker_runner or run_stage_worker_pipeline)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW", fake_pipeline_raw, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_boundary(issues)

    assert any("worker pipeline import" in issue for issue in issues), issues
    assert any("worker pipeline symbol" in issue for issue in issues), issues
    assert any("stage runner type import" in issue for issue in issues), issues
    assert any("stage runner parameter" in issue for issue in issues), issues
    assert any("stage runner forwarding" in issue for issue in issues), issues


def test_pipeline_raw_runtime_encoder_boundary_flags_private_encoder_worker_dependency(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "pipeline_raw_runtime.py"
    fake_runtime.write_text(
        "from app.processing.streaming.encoder import _encoder_worker\n\n"
        "def run_raw_pipeline_runtime():\n"
        "    encoder_thread = threading.Thread(target=_encoder_worker)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_encoder_boundary(issues)

    assert any("pipeline raw encoder worker" in issue for issue in issues), issues


def test_pipeline_raw_runtime_encoder_boundary_flags_public_encoder_worker_dependency(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "pipeline_raw_runtime.py"
    fake_runtime.write_text(
        "from app.processing.streaming.encoder_worker import run_encoder_worker\n\n"
        "def run_raw_pipeline_runtime():\n"
        "    encoder_thread = threading.Thread(target=run_encoder_worker)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_encoder_boundary(issues)

    assert any("encoder worker import" in issue for issue in issues), issues
    assert any("encoder worker target" in issue for issue in issues), issues


def test_pipeline_raw_runtime_completion_boundary_flags_local_completion_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "pipeline_raw_runtime.py"
    fake_runtime.write_text(
        "def run_raw_pipeline_runtime(encoder_thread, error_queue, manifest):\n"
        "    encoder_thread.join()\n"
        "    if not error_queue.empty():\n"
        "        raise error_queue.get()\n"
        "    completed_segments = manifest.read_completed_segments()\n"
        "    return sum(segment.frame_count for segment in completed_segments)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_completion_boundary(issues)

    assert any("encoder thread join" in issue for issue in issues), issues
    assert any("error queue empty check" in issue for issue in issues), issues
    assert any("error queue get" in issue for issue in issues), issues
    assert any("completed segments aggregation" in issue for issue in issues), issues


def test_pipeline_raw_runtime_state_boundary_flags_local_queue_state(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "pipeline_raw_runtime.py"
    fake_runtime.write_text(
        "import queue\n"
        "import threading\n\n"
        "def run_raw_pipeline_runtime():\n"
        "    encode_queue = queue.Queue(maxsize=8)\n"
        "    error_queue = queue.Queue()\n"
        "    stop_event = threading.Event()\n"
        "    return encode_queue, error_queue, stop_event\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_state_boundary(issues)

    assert any("queue import" in issue for issue in issues), issues
    assert any("threading import" in issue for issue in issues), issues
    assert any("queue allocation" in issue for issue in issues), issues
    assert any("stop event allocation" in issue for issue in issues), issues
    assert any("encode queue local" in issue for issue in issues), issues
    assert any("error queue local" in issue for issue in issues), issues
    assert any("stop event local" in issue for issue in issues), issues


def test_pipeline_raw_state_boundary_flags_public_encode_queue_item_alias(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_state = tmp_path / "pipeline_raw_state.py"
    fake_state.write_text(
        "RawEncodeQueueItem = EncodedFrame | SegmentBoundary | StreamEnd | object\n"
        '__all__ = ["RawEncodeQueueItem", "RawPipelineState", "create_raw_pipeline_state"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_STATE", fake_state, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_state_boundary(issues)

    assert any("pipeline raw state public type" in issue for issue in issues), issues
    assert any("RawPipelineState" in issue for issue in issues), issues


def test_pipeline_raw_runtime_stage_boundary_flags_local_worker_runner(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_runtime = tmp_path / "pipeline_raw_runtime.py"
    fake_runtime.write_text(
        "from app.processing.streaming.pipeline_raw_stage import StageWorkerRunner, run_raw_stage_worker\n"
        "from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline\n\n"
        "def run_raw_pipeline_runtime(stage_worker_runner=None):\n"
        "    runner = stage_worker_runner or run_stage_worker_pipeline\n"
        "    run_raw_stage_worker(stage_worker_runner=stage_worker_runner)\n"
        "    runner(input_path='input.mp4')\n"
        '__all__ = ["StageWorkerRunner", "run_raw_pipeline_runtime"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_RUNTIME", fake_runtime, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_runtime_stage_boundary(issues)

    assert any("stage runner type import" in issue for issue in issues), issues
    assert any("stage runner type export" in issue for issue in issues), issues
    assert any("worker pipeline import" in issue for issue in issues), issues
    assert any("worker pipeline symbol" in issue for issue in issues), issues
    assert any("stage runner parameter" in issue for issue in issues), issues
    assert any("stage runner forwarding" in issue for issue in issues), issues
    assert any("runner fallback" in issue for issue in issues), issues
    assert any("runner local" in issue for issue in issues), issues


def test_pipeline_raw_signature_boundary_flags_dead_signature_forwarding(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_dispatch = tmp_path / "pipeline_dispatch.py"
    fake_raw = tmp_path / "pipeline_raw.py"
    fake_runtime = tmp_path / "pipeline_raw_runtime.py"
    fake_raw_encoder = tmp_path / "pipeline_raw_encoder.py"
    fake_encoder_worker = tmp_path / "encoder_worker.py"
    fake_dispatch.write_text(
        "def run_streaming_pipeline(*, signature: str):\n    return run_raw_streaming_pipeline(signature=signature)\n",
        encoding="utf-8",
    )
    fake_raw.write_text(
        "def run_raw_streaming_pipeline(*, signature: str):\n"
        "    return run_raw_pipeline_runtime(signature=signature)\n",
        encoding="utf-8",
    )
    fake_runtime.write_text(
        "def run_raw_pipeline_runtime(*, signature: str):\n    return start_raw_encoder_thread(signature=signature)\n",
        encoding="utf-8",
    )
    fake_raw_encoder.write_text(
        "def start_raw_encoder_thread(*, signature: str):\n"
        "    return threading.Thread(kwargs={'signature': signature})\n",
        encoding="utf-8",
    )
    fake_encoder_worker.write_text("def run_encoder_worker(*, signature: str):\n    del signature\n", encoding="utf-8")
    monkeypatch.setattr(module, "PIPELINE_DISPATCH", fake_dispatch, raising=False)
    monkeypatch.setattr(module, "PIPELINE_RAW", fake_raw, raising=False)
    monkeypatch.setattr(module, "PIPELINE_RAW_RUNTIME", fake_runtime, raising=False)
    monkeypatch.setattr(module, "PIPELINE_RAW_ENCODER", fake_raw_encoder, raising=False)
    monkeypatch.setattr(module, "ENCODER_WORKER", fake_encoder_worker, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_signature_boundary(issues)

    assert any("raw encoder signature" in issue for issue in issues), issues


def test_pipeline_raw_stage_boundary_flags_runner_alias_exports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage = tmp_path / "pipeline_raw_stage.py"
    fake_stage.write_text(
        "from typing import Callable\n\n"
        "StageWorkerRunner = Callable[..., None]\n\n"
        "def run_raw_stage_worker(stage_worker_runner: StageWorkerRunner | None = None):\n"
        "    runner = stage_worker_runner or run_stage_worker_pipeline\n"
        "    runner()\n\n"
        '__all__ = ["StageWorkerRunner", "run_raw_stage_worker"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RAW_STAGE", fake_stage, raising=False)
    issues: list[str] = []

    module._check_pipeline_raw_stage_boundary(issues)

    assert any("runner alias" in issue for issue in issues), issues
    assert any("runner type reference" in issue for issue in issues), issues
    assert any("runner injection parameter" in issue for issue in issues), issues
    assert any("runner fallback" in issue for issue in issues), issues
    assert any("runner export" in issue for issue in issues), issues


def test_streaming_pipeline_lifecycle_boundary_flags_local_resume_and_finalize(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_pipeline.write_text(
        "from app.errors import ResumeConflictError\n"
        "from app.processing.streaming.encoder import _finalize_segmented_output\n"
        "from app.protocol import ndjson\n\n"
        "def process_video_streaming(manifest, ffmpeg):\n"
        "    decision = manifest.prepare('sig', {})\n"
        "    if decision.kind == 'conflict_final_exists':\n"
        "        raise ResumeConflictError(output_path='out.mp4', completed_chunks=0, completed_output_frames=0, sidecar_signature_match=False)\n"
        "    final_output = _finalize_segmented_output()\n"
        "    manifest.cleanup()\n"
        "    ffmpeg.get_frame_count(final_output)\n\n"
        "def _emit_resume_status_event():\n"
        "    ndjson.resume_status(resumed=False, completed_chunks=0, completed_output_frames=0, start_source_frame=0, total_output_frames=1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_streaming_pipeline_lifecycle_boundary(issues)

    assert any("streaming pipeline lifecycle" in issue for issue in issues), issues


def test_streaming_pipeline_preflight_boundary_flags_local_context_building(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_pipeline.write_text(
        "from app.planning import build_signature, build_stage_plan, normalize_processing_steps, resolve_video_info\n"
        "from app.processing.streaming.pipeline_rules import build_config_snapshot, resolved_output_dimensions\n\n"
        "def process_video_streaming(ffmpeg, input_path, output_path):\n"
        "    resolved_steps = normalize_processing_steps([])\n"
        "    video_info = resolve_video_info(ffmpeg, input_path)\n"
        "    stage_plan = build_stage_plan(resolved_steps, video_info['source_frames'], source_duration=video_info['duration'], output_fps=None)\n"
        "    signature = build_signature(input_path=input_path, output_path=output_path, decode_config={}, encode_config={}, workflow_config={}, output_config={}, processing_steps=resolved_steps, video_info=video_info)\n"
        "    config_snapshot = build_config_snapshot(input_path=input_path, output_path=output_path, decode_config={}, encode_config={}, workflow_config={}, output_config={}, processing_steps=resolved_steps, video_info=video_info)\n"
        "    output_width, output_height = resolved_output_dimensions(video_info=video_info, stage_plan=stage_plan, tensor_backend_name='onnx')\n"
        "    segment_frames = max(1, int(0 or 1000))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_streaming_pipeline_preflight_boundary(issues)

    assert any("streaming pipeline preflight" in issue for issue in issues), issues


def test_pipeline_output_dimensions_backend_boundary_flags_dead_backend_forwarding(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rules = tmp_path / "pipeline_rules.py"
    fake_preflight = tmp_path / "pipeline_preflight.py"
    fake_rules.write_text(
        "def resolved_output_dimensions(*, video_info, stage_plan, tensor_backend_name: str):\n"
        "    del tensor_backend_name\n"
        "    return video_info['width'], video_info['height']\n",
        encoding="utf-8",
    )
    fake_preflight.write_text(
        "def build_streaming_pipeline_preflight(*, tensor_backend_name: str):\n"
        "    return resolved_output_dimensions(video_info={}, stage_plan=None, tensor_backend_name=tensor_backend_name)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_RULES", fake_rules, raising=False)
    monkeypatch.setattr(module, "PIPELINE_PREFLIGHT", fake_preflight, raising=False)
    issues: list[str] = []

    module._check_pipeline_output_dimensions_backend_boundary(issues)

    assert any("pipeline output dimensions backend" in issue for issue in issues), issues


def test_streaming_pipeline_dispatch_boundary_flags_local_dispatch_runtime(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_pipeline.write_text(
        "from app.processing.streaming.pipeline_lifecycle import emit_resume_status_event\n"
        "from app.processing.streaming.pipeline_raw import run_raw_streaming_pipeline\n"
        "from app.processing.streaming.stage_file_pipeline import run_stage_file_pipeline\n"
        "from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline\n\n"
        "def _run_streaming_pipeline(use_stage_file_pipeline):\n"
        "    emit_resume_status_event()\n"
        "    if use_stage_file_pipeline:\n"
        "        return run_stage_file_pipeline()\n"
        "    return run_raw_streaming_pipeline(stage_worker_runner=run_stage_worker_pipeline)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_streaming_pipeline_dispatch_boundary(issues)

    assert any("streaming pipeline dispatch" in issue for issue in issues), issues


def test_streaming_pipeline_dispatch_boundary_flags_dispatch_alias_import(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_pipeline.write_text(
        "from app.processing.streaming.pipeline_dispatch import run_streaming_pipeline as _run_streaming_pipeline\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_streaming_pipeline_dispatch_boundary(issues)

    assert any("dispatch alias import" in issue for issue in issues), issues


def test_pipeline_dispatch_runtime_boundary_flags_worker_chain_coupling(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_dispatch = tmp_path / "pipeline_dispatch.py"
    fake_dispatch.write_text(
        "from app.processing.streaming.worker_pipeline import run_stage_worker_pipeline\n\n"
        "def run_streaming_pipeline():\n"
        "    return run_raw_streaming_pipeline(stage_worker_runner=run_stage_worker_pipeline)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_DISPATCH", fake_dispatch, raising=False)
    issues: list[str] = []

    module._check_pipeline_dispatch_runtime_boundary(issues)

    assert any("worker pipeline import" in issue for issue in issues), issues
    assert any("stage worker runner injection" in issue for issue in issues), issues
    assert any("stage worker runner symbol" in issue for issue in issues), issues


def test_pipeline_dispatch_runtime_boundary_flags_duplicate_resume_status_event(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_dispatch = tmp_path / "pipeline_dispatch.py"
    fake_dispatch.write_text(
        "from app.processing.streaming.pipeline_lifecycle import emit_resume_status_event\n\n"
        "def run_streaming_pipeline(use_stage_file_pipeline):\n"
        "    if use_stage_file_pipeline:\n"
        "        emit_resume_status_event(resume_state=None, total_output_frames=0)\n"
        "        return run_stage_file_pipeline()\n"
        "    emit_resume_status_event(resume_state=None, total_output_frames=0)\n"
        "    return run_raw_streaming_pipeline()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PIPELINE_DISPATCH", fake_dispatch, raising=False)
    issues: list[str] = []

    module._check_pipeline_dispatch_runtime_boundary(issues)

    assert any("duplicate resume status event" in issue for issue in issues), issues


def test_encoder_helper_boundary_flags_local_segment_and_finalize_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_encoder = tmp_path / "encoder.py"
    fake_lifecycle = tmp_path / "pipeline_lifecycle.py"
    fake_stage_file = tmp_path / "stage_file_pipeline.py"
    fake_chunk_runtime = tmp_path / "stage_file_chunk_runtime.py"
    fake_encoder.write_text(
        "def _make_segment_progress_callback():\n"
        "    pass\n\n"
        "def _resolve_segment_output_frame_count():\n"
        "    pass\n\n"
        "def _finalize_segmented_output():\n"
        "    pass\n",
        encoding="utf-8",
    )
    fake_lifecycle.write_text(
        "from app.processing.streaming.encoder import _finalize_segmented_output\n",
        encoding="utf-8",
    )
    fake_stage_file.write_text(
        "from app.processing.streaming.encoder import _finalize_segmented_output\n",
        encoding="utf-8",
    )
    fake_chunk_runtime.write_text(
        "from app.processing.streaming.encoder import _resolve_segment_output_frame_count\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENCODER", fake_encoder, raising=False)
    monkeypatch.setattr(module, "PIPELINE_LIFECYCLE", fake_lifecycle, raising=False)
    monkeypatch.setattr(module, "STAGE_FILE_PIPELINE", fake_stage_file)
    monkeypatch.setattr(module, "STAGE_FILE_CHUNK_RUNTIME", fake_chunk_runtime, raising=False)
    issues: list[str] = []

    module._check_encoder_helper_boundary(issues)

    assert any("encoder helper" in issue for issue in issues), issues


def test_encoder_helper_boundary_flags_obsolete_compatibility_entrypoint(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_encoder = tmp_path / "encoder.py"
    fake_encoder.write_text(
        "from app.processing.streaming.encoder_worker import run_encoder_worker as _encoder_worker\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENCODER", fake_encoder, raising=False)
    issues: list[str] = []

    module._check_encoder_helper_boundary(issues)

    assert any("obsolete encoder compatibility entrypoint" in issue for issue in issues), issues


def test_encoder_segment_writer_boundary_flags_local_writer_lifecycle(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_worker = tmp_path / "encoder_worker.py"
    fake_worker.write_text(
        "from pathlib import Path\n\n"
        "def run_encoder_worker():\n"
        "    writer = ffmpeg.open_rawvideo_encoder(output_path='chunk.mp4')\n"
        "    writer.write_frame(frame)\n"
        "    writer.close()\n"
        "    manifest.finalize_chunk('chunk.mp4')\n"
        "    Path('chunk.mp4').unlink(missing_ok=True)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENCODER_WORKER", fake_worker, raising=False)
    issues: list[str] = []

    module._check_encoder_segment_writer_boundary(issues)

    assert any("encoder segment writer" in issue for issue in issues), issues


def test_encoder_finalization_signature_boundary_flags_dead_signature_forwarding(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "pipeline.py"
    fake_lifecycle = tmp_path / "pipeline_lifecycle.py"
    fake_finalization = tmp_path / "encoder_finalization.py"
    fake_stage_file = tmp_path / "stage_file_pipeline.py"
    fake_pipeline.write_text(
        "def process_video_streaming():\n    return finalize_streaming_output(signature=preflight.signature)\n",
        encoding="utf-8",
    )
    fake_lifecycle.write_text(
        "def prepare_streaming_manifest(*, signature: str):\n"
        "    manifest.prepare(signature, {})\n\n"
        "def finalize_streaming_output(*, signature: str):\n"
        "    return finalize_segmented_output(signature=signature)\n",
        encoding="utf-8",
    )
    fake_finalization.write_text(
        "def finalize_segmented_output(*, signature: str):\n    del signature\n",
        encoding="utf-8",
    )
    fake_stage_file.write_text(
        "def run_stage_file_pipeline():\n    return finalize_segmented_output(signature='')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STREAMING_PIPELINE", fake_pipeline, raising=False)
    monkeypatch.setattr(module, "PIPELINE_LIFECYCLE", fake_lifecycle, raising=False)
    monkeypatch.setattr(module, "ENCODER_FINALIZATION", fake_finalization, raising=False)
    monkeypatch.setattr(module, "STAGE_FILE_PIPELINE", fake_stage_file, raising=False)
    issues: list[str] = []

    module._check_encoder_finalization_signature_boundary(issues)

    assert any("encoder finalization signature" in issue for issue in issues), issues


def test_frontend_encode_output_binding_boundary_flags_local_state_and_setters(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_binding = tmp_path / "encode-output-bindings.ts"
    fake_binding.write_text(
        "import { computed } from 'vue'\n"
        "import { CONTAINER_SELECT_OPTIONS, toNumberValue } from '@/services/preset/io-options'\n"
        "import { normalizeOutputDir } from '@/services/preset/normalize'\n"
        "import { normalizeSegmentFrames } from '@/services/preset/io-form-rules'\n\n"
        "const containerOptions = computed(() => CONTAINER_SELECT_OPTIONS)\n"
        "const segmentFramesValue = computed(() => toNumberValue(1000))\n"
        "function setOutputDir(value: string): void { normalizeOutputDir(value) }\n"
        "function setSegmentFrames(value: number): void { normalizeSegmentFrames(value) }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENCODE_OUTPUT_BINDINGS", fake_binding)
    issues: list[str] = []

    module._check_frontend_encode_output_binding_boundary(issues)

    assert any("encode output binding rule" in issue for issue in issues), issues


def test_frontend_defaults_workflow_boundary_flags_local_hydration_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "defaults.ts"
    fake_defaults.write_text(
        "import { pickDefaultInterpolationAlgorithm } from './enhance-rules'\n"
        "import type { InferenceEngine } from '@/types/domain/workflow'\n\n"
        "export function createDefaultWorkbenchPreset(env) {\n"
        "  const workflowConfig = createDefaultWorkflowConfig()\n"
        "  const algorithm = pickDefaultInterpolationAlgorithm(env, workflowConfig.interpolation.tensorBackend)\n"
        "  workflowConfig.interpolation.algorithm = algorithm\n"
        "  const vendor = env?.gpu?.adapters?.[0]?.vendor\n"
        "  const engines = env?.tensorEngines?.[workflowConfig.interpolation.tensorBackend] ?? []\n"
        "  if (vendor === 'nvidia') workflowConfig.interpolation.engine = engines.includes('tensorrt') ? 'tensorrt' : (engines[0] as InferenceEngine)\n"
        "  return { workflowConfig }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PRESET_DEFAULTS", fake_defaults)
    issues: list[str] = []

    module._check_frontend_defaults_workflow_boundary(issues)

    assert any("workflow default rule" in issue for issue in issues), issues


def test_frontend_defaults_workflow_boundary_flags_workflow_default_reexport(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "defaults.ts"
    fake_defaults.write_text(
        "import { createDefaultWorkflowConfig } from './workflow-defaults'\nexport { createDefaultWorkflowConfig }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PRESET_DEFAULTS", fake_defaults)
    issues: list[str] = []

    module._check_frontend_defaults_workflow_boundary(issues)

    assert any("workflow default rule" in issue for issue in issues), issues


def test_frontend_workflow_defaults_factory_boundary_matches_current_repo() -> None:
    module = _load_module()
    issues: list[str] = []

    module._check_frontend_workflow_defaults_factory_boundary(issues)

    assert issues == []


def test_frontend_workflow_defaults_factory_boundary_flags_public_base_factory(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "workflow-defaults.ts"
    fake_defaults.write_text(
        "export function createDefaultWorkflowConfig(): WorkflowConfig { return {} as WorkflowConfig }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKFLOW_DEFAULTS", fake_defaults)
    issues: list[str] = []

    module._check_frontend_workflow_defaults_factory_boundary(issues)

    assert any("base workflow factory" in issue for issue in issues), issues


def test_frontend_workflow_defaults_lookup_boundary_flags_direct_algorithm_lookup(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "workflow-defaults.ts"
    fake_defaults.write_text(
        "const interpolation = env?.interpolationAlgorithms?.find((algorithm) => algorithm.name === selected)\n"
        "const superResolution = env?.superResolutionAlgorithms?.find((algorithm) => algorithm.name === selected)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKFLOW_DEFAULTS", fake_defaults)
    issues: list[str] = []

    module._check_frontend_workflow_defaults_lookup_boundary(issues)

    assert any("workflow defaults lookup" in issue for issue in issues), issues


def test_frontend_workflow_defaults_lookup_boundary_flags_direct_onnx_defaults(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "workflow-defaults.ts"
    fake_defaults.write_text(
        "workflow.interpolation.onnxModel = findInterpolationAlgorithm(env, workflow.interpolation.algorithm)?.onnxModels?.[0] ?? ''\n"
        "workflow.superResolution.onnxModel = findSuperResolutionAlgorithm(env, workflow.superResolution.algorithm)?.onnxModels?.[0] ?? ''\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKFLOW_DEFAULTS", fake_defaults)
    issues: list[str] = []

    module._check_frontend_workflow_defaults_lookup_boundary(issues)

    assert any("direct interpolation ONNX default" in issue for issue in issues), issues
    assert any("direct super-resolution ONNX default" in issue for issue in issues), issues


def test_frontend_workflow_defaults_engine_boundary_flags_local_engine_preference(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "workflow-defaults.ts"
    fake_defaults.write_text(
        "import type { InferenceEngine } from '@/types/domain/workflow'\n"
        "const vendor = env?.gpu?.adapters?.[0]?.vendor\n"
        "const engines = env?.tensorEngines?.[backend] ?? []\n"
        "if (vendor === 'nvidia') workflow.interpolation.engine = engines.includes('tensorrt') ? 'tensorrt' : (engines[0] as InferenceEngine)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "WORKFLOW_DEFAULTS", fake_defaults)
    issues: list[str] = []

    module._check_frontend_workflow_defaults_engine_boundary(issues)

    assert any("workflow defaults engine" in issue for issue in issues), issues


def test_frontend_preset_normalize_boundary_flags_decoder_hardware_reexport(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_normalize = tmp_path / "normalize.ts"
    fake_normalize.write_text(
        "export { resolveDecoderHwaccel } from './decode-hardware'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PRESET_NORMALIZE", fake_normalize)
    issues: list[str] = []

    module._check_frontend_preset_normalize_boundary(issues)

    assert any("preset normalize boundary" in issue for issue in issues), issues


def test_frontend_preset_select_option_type_boundary_flags_local_select_option(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_enhance_options = tmp_path / "enhance-options.ts"
    fake_io_options = tmp_path / "io-options.ts"
    fake_rate_control = tmp_path / "rate-control.ts"
    fake_base_select = tmp_path / "BaseSelect.vue"
    fake_preset_select_options = tmp_path / "select-options.ts"
    fake_enhance_options.write_text(
        "export interface SelectOption { value: string; label: string }\n", encoding="utf-8"
    )
    fake_io_options.write_text("export interface SelectOption { value: string; label: string }\n", encoding="utf-8")
    fake_rate_control.write_text("interface SelectOption { value: string; label: string }\n", encoding="utf-8")
    fake_base_select.write_text("interface SelectOption { value: string; label: string }\n", encoding="utf-8")
    fake_preset_select_options.write_text(
        "export interface SelectOption { value: string; label: string }\n", encoding="utf-8"
    )
    monkeypatch.setattr(module, "PRESET_ENHANCE_OPTIONS", fake_enhance_options, raising=False)
    monkeypatch.setattr(module, "PRESET_IO_OPTIONS", fake_io_options, raising=False)
    monkeypatch.setattr(module, "PRESET_RATE_CONTROL", fake_rate_control, raising=False)
    monkeypatch.setattr(module, "BASE_SELECT", fake_base_select, raising=False)
    monkeypatch.setattr(module, "PRESET_SELECT_OPTIONS", fake_preset_select_options, raising=False)
    issues: list[str] = []

    module._check_frontend_preset_select_option_type_boundary(issues)

    assert any("preset select option type" in issue for issue in issues), issues
    assert any("BaseSelect" in issue for issue in issues), issues
    assert any("obsolete preset select option type" in issue for issue in issues), issues


def test_frontend_select_option_shape_is_shared_from_view_types() -> None:
    module = _load_module()
    base_select_text = (module.FRONTEND_SRC / "components" / "forms" / "BaseSelect.vue").read_text(encoding="utf-8")
    preset_select_options = module.FRONTEND_SRC / "services" / "preset" / "select-options.ts"

    assert not preset_select_options.exists()
    assert "interface SelectOption" not in base_select_text
    assert "@/types/view/select-option" in base_select_text


def test_paddlegan_vsr_contract_flags_backend_frontend_drift() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"ppmsvsr", "edvr"},
        algorithm_metadata={
            "ppmsvsr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "editable_chunk"},
        },
    )

    assert any("metadata" in issue.lower() and "edvr" in issue for issue in issues), issues
