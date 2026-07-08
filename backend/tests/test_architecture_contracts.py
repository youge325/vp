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


def test_enhance_view_option_boundary_flags_view_local_option_rules(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_view = tmp_path / "EnhanceModuleView.vue"
    fake_view.write_text(
        "import { modelOptionLabel } from '@/services/model-metrics'\n"
        "const FPS_MODE_OPTIONS = []\n"
        "function findDetail(details, name) { return details.find((detail) => detail.name === name) }\n"
        "form.interpolationBackend = value as TensorBackend\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ENHANCE_VIEW", fake_view)
    issues: list[str] = []

    module._check_frontend_enhance_option_boundary(issues)

    assert any("enhance option rule" in issue for issue in issues), issues


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
