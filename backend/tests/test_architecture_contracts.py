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
    backend_specs = module._collect_backend_paddlegan_enabled_models()
    backend_disabled = module._collect_backend_paddlegan_disabled_models()
    algorithm_metadata = module._collect_backend_algorithm_metadata()

    issues = module._diff_paddlegan_vsr_contract(backend_specs, backend_disabled, algorithm_metadata)

    assert backend_specs == ALL_PADDLEGAN_VSR_MODELS
    assert backend_disabled == set()
    assert {
        name for name, metadata in algorithm_metadata.items() if metadata["family"] == "paddlegan_vsr"
    } == backend_specs
    assert issues == []


def test_paddlegan_vsr_contract_flags_frontend_reexposing_disabled_model() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"ppmsvsr", "edvr"},
        backend_disabled={"basicvsr"},
        algorithm_metadata={
            "ppmsvsr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "editable_chunk"},
            "edvr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "fixed_window"},
            "basicvsr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "editable_chunk"},
        },
    )

    assert any("disabled" in issue.lower() and "basicvsr" in issue for issue in issues), issues


def test_paddlegan_vsr_contract_flags_missing_metadata() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"ppmsvsr", "edvr"},
        backend_disabled=set(),
        algorithm_metadata={
            "ppmsvsr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "editable_chunk"},
        },
    )

    assert any("edvr" in issue and "metadata" in issue.lower() for issue in issues), issues


def test_paddlegan_vsr_contract_flags_wrong_metadata_shape() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"edvr"},
        backend_disabled=set(),
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
        "def _load_json_arg():\n    pass\n\ndef load_configs():\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CLI_PROCESS_VALIDATION", fake_validation, raising=False)
    issues: list[str] = []

    module._check_cli_process_validation_compat_boundary(issues)

    assert any("CLI process validation compatibility" in issue for issue in issues), issues


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


def test_frontend_enhance_rules_split_boundary_flags_local_rule_bodies(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rules = tmp_path / "enhance-rules.ts"
    fake_rules.write_text(
        "function backendCompatible() {}\n"
        "export function isPaddleGanVsrAlgorithm() {}\n"
        "export function superResolutionInputFrameMode() {}\n"
        "export function fixedRuntimeFrameCount() {}\n"
        "export function fixedSuperResolutionScaleFactor() {}\n"
        "export function applySuperResolutionAlgorithmDefaults() {}\n"
        "export function pickDefaultEngine() {}\n"
        "export function fallbackInterpolationOnnxModel() {}\n"
        "export function fallbackSuperResolutionOnnxModel() {}\n"
        "export function pickDefaultInterpolationAlgorithm() {}\n"
        "export function pickDefaultInterpolationModel() {}\n"
        "export function pickDefaultSuperResolutionAlgorithm() {}\n"
        "export function pickDefaultAnimeProfile() {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_RULES", fake_rules, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_rules_split_boundary(issues)

    assert any("enhance rules split" in issue for issue in issues), issues


def test_frontend_enhance_rules_split_boundary_flags_nested_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rules = tmp_path / "enhance-rules.ts"
    fake_rules.write_text(
        "export * from './enhance-algorithm-capabilities'\n"
        "export * from './enhance-default-selection'\n"
        "export * from './enhance-super-resolution-defaults'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_RULES", fake_rules, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_rules_split_boundary(issues)

    assert any("nested default-selection barrel" in issue for issue in issues), issues


def test_frontend_enhance_rules_split_boundary_flags_obsolete_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rules = tmp_path / "enhance-rules.ts"
    fake_rules.write_text(
        "// Compatibility barrel for enhance rule helpers.\n"
        "export * from './enhance-algorithm-capabilities'\n"
        "export * from './enhance-default-pickers'\n"
        "export * from './enhance-onnx-defaults'\n"
        "export * from './enhance-super-resolution-defaults'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_RULES", fake_rules, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_rules_split_boundary(issues)

    assert any("obsolete enhance rules barrel" in issue for issue in issues), issues


def test_frontend_enhance_default_selection_split_boundary_flags_local_rule_bodies(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "enhance-default-selection.ts"
    fake_defaults.write_text(
        "function backendCompatible() {}\n"
        "export function pickDefaultEngine() {}\n"
        "export function fallbackInterpolationOnnxModel() {}\n"
        "export function fallbackSuperResolutionOnnxModel() {}\n"
        "export function pickDefaultInterpolationAlgorithm() {}\n"
        "export function pickDefaultInterpolationModel() {}\n"
        "export function pickDefaultSuperResolutionAlgorithm() {}\n"
        "export function pickDefaultAnimeProfile() {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_DEFAULT_SELECTION", fake_defaults, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_default_selection_split_boundary(issues)

    assert any("enhance default-selection split" in issue for issue in issues), issues


def test_frontend_enhance_default_selection_split_boundary_flags_obsolete_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_defaults = tmp_path / "enhance-default-selection.ts"
    fake_defaults.write_text(
        "export * from './enhance-default-pickers'\nexport * from './enhance-onnx-defaults'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_DEFAULT_SELECTION", fake_defaults, raising=False)
    issues: list[str] = []

    module._check_frontend_enhance_default_selection_split_boundary(issues)

    assert any("obsolete enhance default-selection barrel" in issue for issue in issues), issues


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


def test_frontend_model_metrics_barrel_boundary_flags_obsolete_reexports(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_model_metrics = tmp_path / "model-metrics.ts"
    fake_model_metrics.write_text(
        "export { formatBytes, modelOptionLabel } from './model-metric-format'\n"
        "export { resolveMetricsForEngine } from './model-engine-metrics'\n"
        "export type { RuntimeMetricEstimate } from './model-runtime-estimates'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "MODEL_METRICS", fake_model_metrics, raising=False)
    issues: list[str] = []

    module._check_frontend_model_metrics_barrel_boundary(issues)

    assert any("obsolete model metrics barrel" in issue for issue in issues), issues


def test_processor_algorithm_boundary_flags_local_algorithm_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_processor = tmp_path / "processor.py"
    fake_processor.write_text(
        "@dataclass(slots=True)\n"
        "class _PipelineAlgorithms:\n"
        "    pass\n\n"
        "def _initialize_algorithms():\n"
        "    pass\n\n"
        "def _pipeline_needs_sequence():\n"
        "    pass\n\n"
        "def _ordered_algorithm_entries():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR", fake_processor)
    issues: list[str] = []

    module._check_processor_algorithm_boundary(issues)

    assert any("processor algorithm rule" in issue for issue in issues), issues


def test_processor_stage_execution_boundary_flags_local_stage_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_processor = tmp_path / "processor.py"
    fake_processor.write_text(
        "def _apply_stage_chain():\n"
        "    pass\n\n"
        "def _apply_pre_steps():\n"
        "    pass\n\n"
        "def _run_sequence_stage():\n"
        "    pass\n\n"
        "def _run_interpolation_sequence_stage():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR", fake_processor)
    issues: list[str] = []

    module._check_processor_stage_execution_boundary(issues)

    assert any("processor stage execution rule" in issue for issue in issues), issues


def test_processor_stream_boundary_flags_local_stream_loops(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_processor = tmp_path / "processor.py"
    fake_processor.write_text(
        "def _process_single_frame_stream():\n"
        "    pass\n\n"
        "def _process_interpolated_stream():\n"
        "    pass\n\n"
        "def _process_sequence_stream():\n"
        "    pass\n\n"
        "def _emit_encoded_payload():\n"
        "    pass\n\n"
        "def _drain_decoded():\n"
        "    pass\n\n"
        "def _emit_stream_end():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR", fake_processor)
    issues: list[str] = []

    module._check_processor_stream_boundary(issues)

    assert any("processor stream rule" in issue for issue in issues), issues


def test_processor_private_reexport_boundary_flags_compatibility_aliases(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_processor = tmp_path / "processor.py"
    fake_processor.write_text(
        "from app.processing.streaming.processor_algorithms import PipelineAlgorithms as _PipelineAlgorithms\n"
        "from app.processing.streaming.processor_stage_execution import run_sequence_stage as _run_sequence_stage\n"
        "from app.processing.streaming.processor_stream_single import process_single_frame_stream as _process_single_frame_stream\n"
        "from app.processing.streaming.stage_runtime import StepAlgorithm as _StepAlgorithm\n\n"
        "__all__ = [\n"
        '    "_PipelineAlgorithms",\n'
        '    "_StepAlgorithm",\n'
        '    "_process_single_frame_stream",\n'
        "]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR", fake_processor)
    issues: list[str] = []

    module._check_processor_private_reexport_boundary(issues)

    assert any("processor private re-export" in issue for issue in issues), issues


def test_processor_stream_aggregator_boundary_flags_local_stream_loops(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_streams = tmp_path / "processor_streams.py"
    fake_streams.write_text(
        "def process_single_frame_stream():\n"
        "    pass\n\n"
        "def process_interpolated_stream():\n"
        "    pass\n\n"
        "def drain_decoded():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR_STREAMS", fake_streams)
    issues: list[str] = []

    module._check_processor_stream_aggregator_boundary(issues)

    assert any("processor stream rule" in issue and "processor_streams.py" in issue for issue in issues), issues


def test_processor_stream_aggregator_boundary_flags_obsolete_compatibility_barrel(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_streams = tmp_path / "processor_streams.py"
    fake_streams.write_text(
        '"""Compatibility exports for queue-driven processor stream loops."""\n\n'
        "from app.processing.streaming.processor_stream_single import process_single_frame_stream\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROCESSOR_STREAMS", fake_streams)
    issues: list[str] = []

    module._check_processor_stream_aggregator_boundary(issues)

    assert any("obsolete processor stream aggregator" in issue for issue in issues), issues


def test_stage_file_pipeline_chunk_boundary_flags_local_chunk_and_rule_helpers(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_pipeline = tmp_path / "stage_file_pipeline.py"
    fake_pipeline.write_text(
        "def _run_single_stage_file_chunks():\n"
        "    pass\n\n"
        "def _run_stage_chunk_to_file():\n"
        "    pass\n\n"
        "def _chunk_progress_adapter():\n"
        "    pass\n\n"
        "def _empty_resume_state():\n"
        "    pass\n\n"
        "def _stage_signature():\n"
        "    pass\n\n"
        "def _safe_stage_name():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_FILE_PIPELINE", fake_pipeline)
    issues: list[str] = []

    module._check_stage_file_pipeline_chunk_boundary(issues)

    assert any("stage file chunk rule" in issue for issue in issues), issues


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


def test_stage_worker_execution_boundary_flags_local_stage_loops(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_stage_worker = tmp_path / "stage_worker.py"
    fake_stage_worker.write_text(
        "def _run_sequence_stage():\n"
        "    pass\n\n"
        "def _run_interpolation_stage():\n"
        "    pass\n\n"
        "def _run_single_frame_stage():\n"
        "    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "STAGE_WORKER", fake_stage_worker)
    issues: list[str] = []

    module._check_stage_worker_execution_boundary(issues)

    assert any("stage worker execution rule" in issue for issue in issues), issues


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


def test_paddlegan_vsr_contract_flags_backend_frontend_drift() -> None:
    module = _load_module()
    issues = module._diff_paddlegan_vsr_contract(
        backend_specs={"ppmsvsr", "edvr"},
        backend_disabled=set(),
        algorithm_metadata={
            "ppmsvsr": {"family": "paddlegan_vsr", "fixedScaleFactor": 4, "inputFrameMode": "editable_chunk"},
        },
    )

    assert any("metadata" in issue.lower() and "edvr" in issue for issue in issues), issues
