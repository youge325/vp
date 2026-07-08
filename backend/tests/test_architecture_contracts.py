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


def test_enhance_form_workflow_rule_boundary_flags_mutation_leaks(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_form = tmp_path / "useEnhanceForm.ts"
    fake_form.write_text("pickDefaultInterpolationAlgorithm(env, 'onnx')\n", encoding="utf-8")
    monkeypatch.setattr(module, "ENHANCE_FORM", fake_form)
    issues: list[str] = []

    module._check_frontend_enhance_workflow_boundary(issues)

    assert any("enhance workflow rule" in issue for issue in issues), issues


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
