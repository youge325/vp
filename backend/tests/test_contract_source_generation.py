"""Regression tests for neutral contract composition and generated aggregates."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from app.generated.contracts import ColorFilterParams
from app.generated.stage_worker_contracts import (
    StageWorkerConfig,
    StageWorkerErrorEvent,
    StageWorkerProgressEvent,
)
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from contract_codegen.application_defaults import (  # noqa: E402
    load_application_defaults,
    render_filter_constraints_typescript,
    render_python_application_defaults,
    render_rust_application_defaults,
    render_typescript_application_defaults,
)
from contract_codegen.model_assets import (  # noqa: E402
    load_model_assets,
    render_python_model_assets,
    render_rust_model_assets,
)
from contract_codegen.python_renderer import (  # noqa: E402
    _render_python_bootstrap_constants,
    _render_python_protocol_constants,
)
from contract_codegen.rust_command_renderer import _render_rust_oneshot_contracts  # noqa: E402
from contract_codegen.rust_renderer import (  # noqa: E402
    _render_rust_error_code_conversion,
    _render_rust_generated_mod,
    _render_rust_task_envelopes,
)
from contract_codegen.schema_composition import (  # noqa: E402
    _render_boundary_schema,
    _render_ndjson_schema,
    _render_stage_worker_schema,
    _render_typescript_boundary_schema,
)
from contract_codegen.schema_tools import validate_explicit_object_boundaries  # noqa: E402
from contract_codegen.typescript_renderer import _render_typescript_events  # noqa: E402
from contract_codegen.validation import (  # noqa: E402
    _validate_backend_command_bindings,
    _validate_termination_reap_bindings,
    validate_contracts,
)


def _load(name: str) -> dict[str, object]:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_application_defaults_are_strict_validated_product_defaults() -> None:
    schema = _load("application-defaults.schema.json")
    defaults = _load("application-defaults.json")
    base_uri = "https://vp-workbench.local/contracts/"
    registry = Registry().with_resources(
        (
            f"{base_uri}{path.name}",
            Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))),
        )
        for path in CONTRACTS.glob("*.schema.json")
    )
    validator = Draft202012Validator(schema, registry=registry)

    validator.validate(defaults)
    assert defaults["interpolation"] == {
        "algorithm": "rife",
        "model": "4.25",
        "onnxModel": "",
        "targetFps": 60,
        "multi": 2,
        "scale": 1,
        "fp16": False,
        "tensorBackend": "pytorch",
        "engine": "cuda",
    }
    assert defaults["superResolution"] == {
        "algorithm": "real-rawvsr-basicvsr",
        "onnxModel": "",
        "scaleFactor": 2,
    }
    assert defaults["workflow"] == {
        "desktopFpsMode": "target",
        "cliFpsMode": "multi",
        "processOrder": "super_resolution_then_interpolation",
    }
    assert defaults["output"]["segmentFrames"] == 1000
    assert defaults["filters"] == {
        "scale": {
            "mode": "factor",
            "factor": 0.5,
            "width": 1920,
            "height": 1080,
            "interpolation": "lanczos4",
        },
        "crop": {"x": 0, "y": 0, "width": 1920, "height": 1080},
        "pad": {"top": 0, "bottom": 0, "left": 0, "right": 0, "color": "#000000"},
        "sharpen": {"amount": 0.5},
        "denoise": {"strength": 10, "colorStrength": 10},
        "color": {"brightness": 0, "contrast": 1, "saturation": 1},
        "animeCleanup": {
            "defaultProfile": "clean-lines",
            "profiles": {
                "clean-lines": {"denoise": 15, "edgeBoost": 30},
                "thin-outline": {"denoise": 8, "edgeBoost": 45},
                "balanced-cel": {"denoise": 25, "edgeBoost": 20},
            },
        },
    }

    invalid = copy.deepcopy(defaults)
    invalid["output"]["segmentFrames"] = -1
    with pytest.raises(ValidationError):
        validator.validate(invalid)

    missing_filter_default = copy.deepcopy(defaults)
    del missing_filter_default["filters"]["scale"]["factor"]
    with pytest.raises(ValidationError):
        validator.validate(missing_filter_default)

    invalid_profile_strength = copy.deepcopy(defaults)
    invalid_profile_strength["filters"]["animeCleanup"]["profiles"]["clean-lines"]["denoise"] = 101
    with pytest.raises(ValidationError):
        validator.validate(invalid_profile_strength)

    extra = copy.deepcopy(defaults)
    extra["legacyDefault"] = True
    with pytest.raises(ValidationError):
        validator.validate(extra)


def _write_model_asset_fixture(directory: Path, assets: dict[str, object]) -> None:
    for name in ("model-assets.schema.json", "tensor-backend.schema.json", "inference-engine.schema.json"):
        (directory / name).write_text((CONTRACTS / name).read_text(encoding="utf-8"), encoding="utf-8")
    (directory / "model-assets.json").write_text(json.dumps(assets), encoding="utf-8")


def test_model_asset_manifest_is_strict_and_normalized(tmp_path: Path) -> None:
    assets = load_model_assets(CONTRACTS)
    families = assets["families"]

    assert [family["algorithmId"] for family in families] == [
        "real-rawvsr-basicvsr",
        "real-rawvsr-edvr",
        "real-rawvsr-tdan",
        "real-rawvsr-toflow",
    ]
    assert assets["license"]["usage"] == "non_commercial"
    assert assets["runtime"] == {
        "algorithmFamily": "pytorch_vsr",
        "tensorBackend": "pytorch",
        "engines": ["cuda"],
    }
    for family in families:
        assert [variant["scaleFactor"] for variant in family["variants"]] == [2, 3, 4]
        assert all(len(variant["sourceSha256"]) == 64 for variant in family["variants"])
        assert all(len(variant["inferenceSha256"]) == 64 for variant in family["variants"])
        assert all(variant["parameterCount"] > 0 for variant in family["variants"])

    invalid = copy.deepcopy(assets)
    del invalid["families"][0]["variants"][0]["sourceSha256"]
    _write_model_asset_fixture(tmp_path, invalid)
    with pytest.raises(ValidationError):
        load_model_assets(tmp_path)


def test_model_asset_generation_is_order_independent_and_rejects_duplicates(tmp_path: Path) -> None:
    canonical = load_model_assets(CONTRACTS)
    unordered = copy.deepcopy(canonical)
    unordered["families"].reverse()
    for family in unordered["families"]:
        family["variants"].reverse()
    _write_model_asset_fixture(tmp_path, unordered)
    normalized = load_model_assets(tmp_path)
    assert normalized == canonical
    assert render_python_model_assets(normalized) == render_python_model_assets(canonical)
    assert render_rust_model_assets(normalized) == render_rust_model_assets(canonical)

    duplicate_algorithm = copy.deepcopy(canonical)
    duplicate_algorithm["families"][1]["algorithmId"] = duplicate_algorithm["families"][0]["algorithmId"]
    _write_model_asset_fixture(tmp_path, duplicate_algorithm)
    with pytest.raises(RuntimeError, match="algorithm IDs must be unique"):
        load_model_assets(tmp_path)

    duplicate_scale = copy.deepcopy(canonical)
    duplicate_scale["families"][0]["variants"][1]["scaleFactor"] = 2
    _write_model_asset_fixture(tmp_path, duplicate_scale)
    with pytest.raises(RuntimeError, match="scale factors must be unique"):
        load_model_assets(tmp_path)

    duplicate_path = copy.deepcopy(canonical)
    duplicate_path["families"][1]["variants"][0]["relativePath"] = canonical["families"][0]["variants"][0][
        "relativePath"
    ]
    _write_model_asset_fixture(tmp_path, duplicate_path)
    with pytest.raises(RuntimeError, match="runtime path must be"):
        load_model_assets(tmp_path)


def test_model_asset_bindings_include_runtime_integrity_data() -> None:
    assets = load_model_assets(CONTRACTS)

    python_output = render_python_model_assets(assets)
    rust_output = render_rust_model_assets(assets)

    assert "REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM" in python_output
    assert "19e06889ff7e96f3904c24562667949bb7e452ab02234508db51759741c91efb" in python_output
    assert "REAL_RAWVSR_MODEL_FAMILIES" in rust_output
    assert "models/super_resolution/pytorch/real-rawvsr-toflow/x4/model.safetensors" in rust_output


def test_application_defaults_generate_language_native_read_only_constants() -> None:
    defaults = load_application_defaults(CONTRACTS, load_model_assets(CONTRACTS))

    assert defaults["superResolution"] == {
        "algorithm": "real-rawvsr-basicvsr",
        "onnxModel": "",
        "scaleFactor": 2,
        "numFrames": 10,
        "tensorBackend": "pytorch",
        "engine": "cuda",
    }

    python_output = render_python_application_defaults(defaults)
    typescript_output = render_typescript_application_defaults(defaults)
    rust_output = render_rust_application_defaults(defaults)
    filter_constraints = render_filter_constraints_typescript(CONTRACTS)

    assert 'DEFAULT_RIFE_MODEL_VERSION: Final = "4.25"' in python_output
    assert "DEFAULT_SEGMENT_FRAMES: Final = 1000" in python_output
    assert "FILTER_DEFAULTS: Final = MappingProxyType" in python_output
    assert '"clean-lines": MappingProxyType({"denoise": 15, "edgeBoost": 30})' in python_output
    assert "export const APPLICATION_DEFAULTS =" in typescript_output
    assert '"segmentFrames": 1000' in typescript_output
    assert 'DEFAULT_RIFE_MODEL_VERSION: &str = "4.25"' in rust_output
    assert "export const FILTER_FIELD_CONSTRAINTS =" in filter_constraints
    assert '"amount": {"minimum": 0, "maximum": 1}' in filter_constraints
    assert '"profile": {"enum": ["clean-lines", "thin-outline", "balanced-cel"]}' in filter_constraints


def test_python_generated_package_contains_only_declared_contract_outputs() -> None:
    generated = REPO_ROOT / "backend/app/generated"
    assert {path.name for path in generated.glob("*.py") if path.name != "__init__.py"} == {
        "application_defaults.py",
        "bootstrap_constants.py",
        "contracts.py",
        "model_assets.py",
        "protocol_constants.py",
        "stage_worker_contracts.py",
    }


def test_source_contract_references_resolve_and_preserve_named_filter_boundaries() -> None:
    validate_contracts()
    aggregate = json.loads(_render_boundary_schema())
    definitions = aggregate["$defs"]

    assert definitions["PreprocessConfig"] == definitions["PostprocessConfig"]
    assert definitions["PreprocessConfig"]["type"] == "object"
    assert definitions["PreprocessConfig"]["properties"]["filters"]["items"] == {"$ref": "#/$defs/FilterStep"}


def test_contract_validation_rejects_implicit_object_openness() -> None:
    with pytest.raises(RuntimeError, match="additionalProperties.*#/properties/nested"):
        validate_explicit_object_boundaries(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {},
                    }
                },
            },
            source_name="example.schema.json",
        )


def test_ndjson_schema_reuses_payload_property_schemas() -> None:
    schema = json.loads(_render_ndjson_schema(validate_contracts()))
    expected_sources = (
        ("task-progress.schema.json", ""),
        ("task-completed.schema.json", ""),
        ("backend-task-error.schema.json", ""),
        ("resume-status.schema.json", ""),
        ("video-info.schema.json", ""),
        ("environment.schema.json", "/$defs/EnvironmentCheckResult"),
        ("resume-inspection.schema.json", ""),
    )

    for variant, (source_name, pointer) in zip(schema["oneOf"], expected_sources, strict=True):
        for property_name, property_schema in variant["properties"].items():
            if property_name != "type":
                assert property_schema == {"$ref": f"./{source_name}#{pointer}/properties/{property_name}"}

    assert [variant["properties"]["type"]["const"] for variant in schema["oneOf"]] == [
        "progress",
        "completed",
        "error",
        "resume_status",
        "info",
        "check",
        "resume_inspection",
    ]


def test_protocol_constants_are_generated_from_the_manifest() -> None:
    manifest = validate_contracts()
    rendered = _render_python_protocol_constants(manifest)
    bootstrap = _render_python_bootstrap_constants(manifest)

    assert 'TERMINAL_PROGRESS_PREFIX = "[VP_PROGRESS]"' in rendered
    assert 'STAGE_WORKER_EVENT_PREFIX = "VP_STAGE_EVENT "' in rendered
    assert 'TENSORRT_LOG_PREFIX = "[VP_TRT]"' in rendered
    assert 'STAGE_WORKER_COMMAND = ("-m", "app")' in rendered
    assert 'STAGE_WORKER_SUBCOMMAND = "stage-worker"' in rendered
    assert 'STAGE_WORKER_CONFIG_FLAG = "--config-json"' in rendered
    assert "TERMINATION_REAP_TIMEOUT_MS = 5000" in rendered
    assert "STAGE_WORKER_TERMINATION_REAP_TIMEOUT_MS = TERMINATION_REAP_TIMEOUT_MS" in rendered
    assert "from app.generated.bootstrap_constants import (" in rendered
    assert "NDJSON_LINE_LIMIT_BYTES = 1048576" not in rendered
    assert "ERROR_SUMMARY_LIMIT_BYTES = 8192" not in rendered
    assert "NDJSON_LINE_LIMIT_BYTES = 1048576" in bootstrap
    assert "ERROR_SUMMARY_LIMIT_BYTES = 8192" in bootstrap
    assert "ONE_SHOT_STDOUT_LIMIT_BYTES = 8388608" in rendered
    typescript = _render_typescript_events(manifest)
    assert "TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'" in typescript
    assert "TENSORRT_LOG_PREFIX = '[VP_TRT]'" in typescript


def test_rust_backend_protocol_adapters_are_generated_from_the_manifest() -> None:
    manifest = validate_contracts()
    one_shot = _render_rust_oneshot_contracts(manifest)
    task_envelopes = _render_rust_task_envelopes(manifest)

    assert "pub(crate) trait BackendCommandSpec: private::Sealed" in one_shot
    assert "pub(crate) trait BackendOneShotSpec: BackendCommandSpec" in one_shot
    assert "pub(crate) trait BackendProcessSpec: BackendCommandSpec" in one_shot
    assert "type Invocation;" in one_shot
    assert "fn arguments(invocation: &Self::Invocation) -> Vec<String>;" in one_shot
    assert "pub(crate) struct InspectVideoSpec;" in one_shot
    assert "pub(crate) struct InspectVideoInvocation" in one_shot
    assert "type Output = VideoInfo;" in one_shot
    assert 'const SUBCOMMAND: &\'static str = "info";' in one_shot
    assert "const TOTAL_TIMEOUT: Duration = Duration::from_millis(30000);" in one_shot
    assert one_shot.count("const TERMINATION_TIMEOUT: Duration = Duration::from_millis(5000);") == 4
    assert "const TERMINATION_TIMEOUT: Duration = TERMINATION_REAP_TIMEOUT;" not in one_shot
    assert "pub(crate) struct StartTaskSpec;" in one_shot
    assert "pub(crate) struct StartTaskInvocation" in one_shot
    assert "type Input = RuntimeConfigBundle;" in one_shot
    assert "type Event = BackendTaskEnvelope;" in one_shot
    assert "const IPC_COMMAND" not in one_shot
    assert "const TOTAL_TIMEOUT: Option<Duration>" not in one_shot
    assert "pub(crate) const NDJSON_LINE_LIMIT_BYTES: usize = 1048576;" in one_shot
    assert "backend_oneshot_contract" not in one_shot
    assert task_envelopes.count("#[serde(rename = ") == 4
    assert "Progress(TaskProgressPayload)" in task_envelopes
    assert "ResumeStatus(ResumeStatusPayload)" in task_envelopes


def test_rust_process_event_type_is_generated_from_the_manifest() -> None:
    manifest = validate_contracts()
    manifest["backendProcessCommand"]["eventPayload"] = "TypedProcessEvent"

    one_shot = _render_rust_oneshot_contracts(manifest)
    task_envelopes = _render_rust_task_envelopes(manifest)
    generated_mod = _render_rust_generated_mod(manifest)

    assert "use crate::generated::backend_task_envelope::TypedProcessEvent;" in one_shot
    assert "type Event = TypedProcessEvent;" in one_shot
    assert "pub(crate) enum TypedProcessEvent" in task_envelopes
    assert "pub(crate) use backend_task_envelope::TypedProcessEvent;" not in generated_mod
    assert "BackendTaskEnvelope" not in one_shot
    assert "BackendTaskEnvelope" not in task_envelopes


def test_rust_classifier_consumes_the_generated_process_event_associated_type() -> None:
    classifier = (REPO_ROOT / "frontend/src-tauri/src/tasks/envelope.rs").read_text(encoding="utf-8")

    assert "type NdjsonEnvelope = <StartTaskSpec as BackendProcessSpec>::Event;" in classifier
    assert "BackendTaskEnvelope as NdjsonEnvelope" not in classifier


def test_backend_command_bindings_reject_result_input_and_cli_drift() -> None:
    manifest = validate_contracts()
    definitions = json.loads(_render_boundary_schema())["$defs"]

    process_result = copy.deepcopy(manifest)
    next(command for command in process_result["commands"] if command["name"] == "start_task")["result"] = "VideoInfo"
    with pytest.raises(RuntimeError, match="process IPC command must return void"):
        _validate_backend_command_bindings(process_result, definitions)

    one_shot_result = copy.deepcopy(manifest)
    next(command for command in one_shot_result["commands"] if command["name"] == "inspect_video")["result"] = (
        "ResumeInspectionResult"
    )
    with pytest.raises(RuntimeError, match="backend payload VideoInfo is not represented"):
        _validate_backend_command_bindings(one_shot_result, definitions)

    cli_field = copy.deepcopy(manifest)
    cli_field["backendOneShotCommands"][0]["cliArguments"][0]["field"] = "unknownInput"
    with pytest.raises(RuntimeError, match="CLI field unknownInput is not reachable"):
        _validate_backend_command_bindings(cli_field, definitions)

    cli_optionality = copy.deepcopy(manifest)
    cli_optionality["backendProcessCommand"]["cliArguments"][2]["optional"] = False
    with pytest.raises(RuntimeError, match="type/optionality does not match"):
        _validate_backend_command_bindings(cli_optionality, definitions)

    nested_type = copy.deepcopy(definitions)
    nested_type["TaskRequest"]["properties"]["resumeMode"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"nested": {"$ref": "#/$defs/ResumeMode"}},
    }
    with pytest.raises(RuntimeError, match="type/optionality does not match"):
        _validate_backend_command_bindings(manifest, nested_type)

    stdin_payload = copy.deepcopy(manifest)
    stdin_payload["backendOneShotCommands"][2]["stdinPayload"] = "EnvironmentCheckResult"
    with pytest.raises(RuntimeError, match="stdin payload is not derivable"):
        _validate_backend_command_bindings(stdin_payload, definitions)


def test_backend_command_reap_deadline_bindings_reject_drift() -> None:
    manifest = validate_contracts()

    for entry in [manifest["backendProcessCommand"], *manifest["backendOneShotCommands"]]:
        assert entry["deadlines"]["terminationReapLimit"] == "terminationReapMs"

    mutated = copy.deepcopy(manifest)
    mutated["backendOneShotCommands"][0]["deadlines"]["terminationReapLimit"] = "missingLimit"
    with pytest.raises(RuntimeError, match="info termination/reap deadline references an unknown protocol limit"):
        _validate_termination_reap_bindings(mutated)


def test_runtime_and_stage_worker_contracts_are_strict_generated_boundaries() -> None:
    boundary = json.loads(_render_boundary_schema())
    runtime = boundary["$defs"]["RuntimeConfigBundle"]
    assert runtime["required"] == ["decode", "workflow", "encode", "output"]
    assert runtime["additionalProperties"] is False
    assert boundary["$defs"]["OutputConfig"]["properties"]["outputDir"]["pattern"] == r"\S"

    worker = json.loads(_render_stage_worker_schema(load_model_assets(CONTRACTS)))
    definitions = worker["$defs"]
    assert definitions["StageWorkerConfig"]["additionalProperties"] is False
    assert definitions["StageWorkerConfig"]["properties"]["stageIndex"]["minimum"] == 1
    assert definitions["StageWorkerProgressEvent"]["properties"]["type"] == {"const": "progress"}
    assert definitions["StageWorkerErrorEvent"]["properties"]["type"] == {"const": "error"}
    vsr_properties = definitions["StageWorkerPytorchVsrKwargs"]["properties"]
    assert vsr_properties["sr_algorithm"]["enum"] == [
        "real-rawvsr-basicvsr",
        "real-rawvsr-edvr",
        "real-rawvsr-tdan",
        "real-rawvsr-toflow",
    ]
    assert vsr_properties["scale_factor"]["enum"] == [2, 3, 4]
    assert vsr_properties["engine"] == {"const": "cuda"}


def test_optional_filter_parameters_allow_missing_but_reject_explicit_null() -> None:
    assert ColorFilterParams.model_validate({}).brightness is None
    with pytest.raises(PydanticValidationError):
        ColorFilterParams.model_validate({"brightness": None})


def test_typescript_boundary_omits_only_the_backend_runtime_bundle() -> None:
    full = json.loads(_render_boundary_schema())
    typescript = json.loads(_render_typescript_boundary_schema())

    assert "RuntimeConfigBundle" in full["$defs"]
    assert "RuntimeConfigBundle" not in typescript["$defs"]
    assert "RuntimeConfigBundle" not in typescript["properties"]
    assert "RuntimeConfigBundle" not in typescript["required"]
    assert set(full["$defs"]) - set(typescript["$defs"]) == {"RuntimeConfigBundle"}
    for name in ("DecodeConfig", "WorkflowConfig", "EncodeConfig", "OutputConfig"):
        assert typescript["$defs"][name] == full["$defs"][name]
    generated_typescript = (REPO_ROOT / "frontend/src/types/generated/contracts.ts").read_text(encoding="utf-8")
    assert "RuntimeConfigBundle" not in generated_typescript


def test_rust_error_code_conversion_is_exhaustive_and_has_no_json_round_trip() -> None:
    rendered = _render_rust_error_code_conversion()

    assert "BackendTaskErrorCode::MissingFfmpeg => TaskErrorCode::MissingFfmpeg" in rendered
    assert "BackendTaskErrorCode::PersistenceFailed => TaskErrorCode::PersistenceFailed" in rendered
    assert "serde_json" not in rendered


def test_stage_worker_generated_models_reject_coercion_negative_values_and_extras() -> None:
    valid_config = {
        "stage": {
            "algorithm_type": "frame_filter_chain",
            "algorithm_kwargs": {"filters": []},
        },
        "stageIndex": 1,
        "stageTotal": 1,
        "stageName": "01_filter",
        "inputWidth": 320,
        "inputHeight": 180,
        "outputWidth": 320,
        "outputHeight": 180,
        "inputFrameCount": 2,
        "tensorBackendName": None,
        "outputFrameCount": 2,
    }

    assert StageWorkerConfig.model_validate(valid_config).stage_index == 1
    for invalid in (
        {**valid_config, "stageIndex": True},
        {**valid_config, "inputFrameCount": -1},
        {**valid_config, "unexpected": 1},
    ):
        with pytest.raises(PydanticValidationError):
            StageWorkerConfig.model_validate(invalid)

    valid_progress = {
        "type": "progress",
        "stageName": "01_filter",
        "stageIndex": 1,
        "stageTotal": 1,
        "current": 0,
        "total": 1,
        "heartbeat": False,
        "force": False,
    }
    assert StageWorkerProgressEvent.model_validate(valid_progress).current == 0
    for invalid in (
        {**valid_progress, "type": "error"},
        {**valid_progress, "heartbeat": None},
        {**valid_progress, "force": None},
        {key: value for key, value in valid_progress.items() if key != "heartbeat"},
        {key: value for key, value in valid_progress.items() if key != "force"},
    ):
        with pytest.raises(PydanticValidationError):
            StageWorkerProgressEvent.model_validate(invalid)

    valid_error = {
        "type": "error",
        "code": "invalid_config",
        "message": "invalid worker config",
        "details": None,
    }
    assert StageWorkerErrorEvent.model_validate(valid_error).code == "invalid_config"
    for invalid in (
        {**valid_error, "code": "not_a_backend_code"},
        {**valid_error, "unexpected": True},
    ):
        with pytest.raises(PydanticValidationError):
            StageWorkerErrorEvent.model_validate(invalid)


def test_manifest_v6_declares_all_backend_command_policies_without_expanding_ipc() -> None:
    manifest = validate_contracts()

    assert manifest["schemaVersion"] == 6
    assert len(manifest["commands"]) == 10
    assert manifest["backendProcessCommand"]["stdinPayload"] == "RuntimeConfigBundle"
    assert manifest["backendProcessCommand"]["stdinField"] == "config"
    assert manifest["backendProcessCommand"]["cliArguments"] == [
        {"flag": "--input", "field": "inputPath", "valueType": "string"},
        {"flag": "--config-stdin"},
        {"flag": "--resume-mode", "field": "resumeMode", "valueType": "ResumeMode", "optional": True},
    ]
    assert manifest["stageWorkerCommand"] == {
        "command": ["-m", "app"],
        "subcommand": "stage-worker",
        "configFlag": "--config-json",
        "input": {
            "configPayload": "StageWorkerConfig",
            "stdinStream": "rawvideo-bytes",
        },
        "output": {
            "stdoutStream": "rawvideo-bytes",
            "stderrPayloads": ["StageWorkerProgressEvent", "StageWorkerErrorEvent"],
        },
        "deadlines": {
            "totalMs": None,
            "terminationReapLimit": "terminationReapMs",
        },
    }
    assert [entry["deadlines"]["totalMs"] for entry in manifest["backendOneShotCommands"]] == [
        30_000,
        180_000,
        60_000,
    ]
    assert all(
        entry["deadlines"]["terminationReapLimit"] == "terminationReapMs"
        for entry in [manifest["backendProcessCommand"], *manifest["backendOneShotCommands"]]
    )


def test_ndjson_external_references_validate_real_envelopes() -> None:
    schema = _load("ndjson.schema.json")
    base_uri = "https://vp-workbench.local/contracts/"
    registry = Registry().with_resources(
        (
            f"{base_uri}{path.name}",
            Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))),
        )
        for path in CONTRACTS.glob("*.schema.json")
    )
    validator = Draft202012Validator(schema, registry=registry)
    envelopes = [
        {
            "type": "progress",
            "current": 1,
            "total": 2,
            "percent": 50.0,
            "stage": "Encoding",
            "stageIndex": 1,
            "stageTotal": 1,
        },
        {
            "type": "completed",
            "outputPath": "output.mp4",
            "processedFrames": 20,
            "timeSeconds": 1.5,
        },
        {
            "type": "error",
            "code": "invalid_input",
            "message": "invalid video",
            "details": None,
        },
        {
            "type": "resume_status",
            "resumed": True,
            "completedChunks": 2,
            "completedOutputFrames": 10,
            "startSourceFrame": 5,
            "totalOutputFrames": 20,
        },
        {
            "type": "info",
            "fps": 24.0,
            "width": 1920,
            "height": 1080,
            "videoCodec": "h264",
        },
        {
            "type": "check",
            "ffmpeg": {
                "available": True,
                "hwaccels": [],
                "encoderProfiles": [],
                "decoderProfiles": [],
            },
            "gpu": {"adapters": []},
            "tensorEngines": {"pytorch": [], "paddle": [], "onnx": []},
            "interpolationAlgorithms": [],
            "superResolutionAlgorithms": [],
            "runtimeMode": "external",
        },
        {
            "type": "resume_inspection",
            "pipeline_kind": "streaming",
            "outputPath": "output.mp4",
            "input_path": "input.mp4",
            "finalExists": False,
            "sidecarExists": True,
            "signatureMatch": True,
            "completedChunks": 2,
            "completedOutputFrames": 10,
            "nextSourceFrame": 5,
            "totalOutputFrames": 20,
        },
    ]

    for envelope in envelopes:
        validator.validate(envelope)

    with pytest.raises(ValidationError):
        validator.validate({**envelopes[0], "unexpected": 0})
    with pytest.raises(ValidationError):
        validator.validate({**envelopes[-1], "completedChunks": -1})
