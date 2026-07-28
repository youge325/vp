"""CLI processing-step planning tests."""

import argparse
import io
import json
from types import SimpleNamespace

import pytest

from app.cli.commands.check import cmd_check
from app.cli.commands._process_execution import _run_format_conversion
from app.cli.commands._process_planning import PreparedRun
from app.cli.commands._process_validation import load_runtime_configs
from app.cli.parser import build_parser
from app.config import settings
from app.errors import ProcessError, TaskErrorCode
from app.models import WorkflowConfig
from app.planning import (
    ProcessingStep,
    StageProjection,
    build_stage_plan,
    build_run_identity,
)
from app.ports.media import VideoMetadata
from tests.support.workflow_configs import make_workflow_config as _make_workflow_config


def test_prepared_run_does_not_duplicate_derived_pipeline_facts() -> None:
    assert "output_dir" not in PreparedRun.__dataclass_fields__
    assert "processing_steps" not in PreparedRun.__dataclass_fields__
    assert "final_output_fps" not in PreparedRun.__dataclass_fields__


def test_format_conversion_forwards_projected_target_fps_to_ffmpeg(tmp_path) -> None:
    class FakeFfmpeg:
        def __init__(self) -> None:
            self.transcode_kwargs = {}

        def transcode_video(self, **kwargs) -> None:
            self.transcode_kwargs = kwargs

        def get_frame_count(self, _input_path: str) -> int:
            return 24

    configs = load_runtime_configs(
        _make_runtime_args(
            algorithm="format_conversion",
            fps_mode="target",
            target_fps=24.0,
            output_dir=str(tmp_path),
        )
    )
    resolved_workflow, projection, output_fps = StageProjection.resolve_workflow(
        configs.json_section("workflow"),
        source_fps=60.0,
    )
    configs = configs.with_workflow(WorkflowConfig.model_validate(resolved_workflow))
    stage_plan = build_stage_plan(
        projection,
        60,
        source_duration=1.0,
        output_fps=output_fps,
    )
    assert stage_plan.steps == ()
    assert output_fps == 24.0

    prepared = PreparedRun(
        output_path=str(tmp_path / "target-fps.mp4"),
        runtime_configs=configs,
        preflight=SimpleNamespace(stage_plan=stage_plan),
    )
    observers = SimpleNamespace(progress_reporter=SimpleNamespace(update=lambda *_args, **_kwargs: None))
    ffmpeg = FakeFfmpeg()

    _run_format_conversion(
        ffmpeg=ffmpeg,
        input_path="input.mp4",
        prepared=prepared,
        observers=observers,
        resume_mode="auto",
    )

    assert ffmpeg.transcode_kwargs["output_fps"] == 24.0


class _FakeCheckFFmpeg:
    discovered_gpu_adapters = None

    def is_available(self) -> bool:
        return True

    def discover_capabilities(self, gpu_adapters):
        type(self).discovered_gpu_adapters = gpu_adapters
        return {"hwaccels": [], "encoderProfiles": [], "decoderProfiles": []}


def _make_runtime_args(**overrides):
    values = {
        "config_stdin": False,
        "algorithm": "frame_interpolation",
        "enable_interpolation": False,
        "enable_super_resolution": False,
        "process_order": "super_resolution_then_interpolation",
        "fps": 60.0,
        "fps_mode": "multi",
        "target_fps": 60.0,
        "codec": "libx264",
        "crf": 18,
        "preset": "medium",
        "backend": "pytorch",
        "output_dir": "D:/output",
        "multi": None,
        "model": None,
        "scale": None,
        "fp16": None,
        "sr_scale_factor": 2.0,
        "sr_algorithm": "placeholder",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _load_stdin_configs(monkeypatch: pytest.MonkeyPatch, payload: dict, **arg_overrides):
    monkeypatch.setattr(
        "app.cli.commands._process_validation.sys.stdin",
        io.StringIO(json.dumps(payload)),
    )
    return load_runtime_configs(_make_runtime_args(config_stdin=True, **arg_overrides))


def test_stage_projection_builds_interpolation_mode():
    steps = StageProjection.from_workflow(_make_workflow_config()).steps

    assert [step.algorithm_type for step in steps] == ["frame_interpolation"]
    assert steps[0].algorithm_kwargs["multi"] == 2
    assert steps[0].stage_name == "01_frame_interpolation"


def test_stage_projection_builds_combined_order():
    steps = StageProjection.from_workflow(
        _make_workflow_config(
            processOrder="frame_interpolation_then_super_resolution",
            superResolution={
                "enabled": True,
                "scaleFactor": 2.0,
                "algorithm": "placeholder",
            },
        )
    ).steps

    assert [step.algorithm_type for step in steps] == [
        "frame_interpolation",
        "super_resolution",
    ]
    assert steps[0].algorithm_kwargs["model_version"] == "4.25"
    assert steps[1].algorithm_kwargs["scale_factor"] == 2.0


def test_stage_projection_format_conversion_skips_frame_filters():
    steps = StageProjection.from_workflow(
        _make_workflow_config(
            interpolation={
                "enabled": False,
                "targetFps": 60,
                "multi": 2,
                "model": "4.25",
                "scale": 1.0,
                "fp16": False,
                "tensorBackend": "pytorch",
            },
            superResolution={"enabled": False, "scaleFactor": 2.0, "algorithm": "placeholder"},
        )
    ).steps

    assert steps == ()


def test_processing_step_json_shape_is_stable_and_defensive():
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2, "model_version": "4.25"},
        stage_name="01_frame_interpolation",
    )

    payload = step.to_jsonable()
    assert payload == {
        "algorithm_type": "frame_interpolation",
        "algorithm_kwargs": {"multi": 2, "model_version": "4.25"},
        "stage_name": "01_frame_interpolation",
    }

    payload["algorithm_kwargs"]["multi"] = 3
    assert step.algorithm_kwargs["multi"] == 2


def test_processing_step_freezes_nested_algorithm_configuration():
    step = ProcessingStep(
        algorithm_type="frame_filter_chain",
        algorithm_kwargs={"filters": [{"kind": "scale", "params": {"factor": 2}}]},
        stage_name="01_preprocess",
    )

    with pytest.raises(TypeError):
        step.algorithm_kwargs["filters"][0]["params"]["factor"] = 4
    assert step.to_jsonable()["algorithm_kwargs"]["filters"][0]["params"]["factor"] == 2


def test_load_runtime_configs_returns_typed_models_and_wire_shape():
    configs = load_runtime_configs(_make_runtime_args(output_dir="D:/typed-output"))

    assert configs.decode.mode == "software"
    assert configs.workflow.interpolation.tensor_backend == "pytorch"
    assert configs.output.output_dir == "D:/typed-output"

    sections = configs.json_sections()
    assert sections["decode"]["mode"] == "software"
    assert sections["decode"]["hwaccelDevice"] is None
    assert sections["encode"]["keepAudio"] is True
    assert sections["workflow"]["interpolation"]["tensorBackend"] == "pytorch"
    assert sections["output"]["outputDir"] == "D:/typed-output"


def test_runtime_config_json_sections_are_defensive_copies():
    configs = load_runtime_configs(_make_runtime_args(output_dir="D:/wire-output"))
    sections = configs.json_sections()

    assert sections["decode"]["decoder"] == "software"
    assert sections["encode"]["rateControl"] == {"mode": "crf", "value": 18}
    assert sections["workflow"]["processOrder"] == "super_resolution_then_interpolation"
    assert sections["output"]["outputDir"] == "D:/wire-output"

    sections["workflow"]["interpolation"]["multi"] = 99
    assert configs.json_section("workflow")["interpolation"]["multi"] == 2


def test_load_runtime_configs_rejects_missing_output_dir():
    with pytest.raises(ProcessError) as exc_info:
        load_runtime_configs(_make_runtime_args(output_dir=None))

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "outputDir" in exc_info.value.message


def test_load_runtime_configs_rejects_invalid_stdin_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.cli.commands._process_validation.sys.stdin",
        io.StringIO("{not json"),
    )

    with pytest.raises(ProcessError) as exc_info:
        load_runtime_configs(_make_runtime_args(config_stdin=True))

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "Invalid stdin JSON" in exc_info.value.message


def test_load_runtime_configs_rejects_non_object_stdin_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.cli.commands._process_validation.sys.stdin",
        io.StringIO('{"workflow": []}'),
    )

    with pytest.raises(ProcessError) as exc_info:
        load_runtime_configs(_make_runtime_args(config_stdin=True))

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "workflow" in exc_info.value.message


def test_runtime_config_workflow_update_keeps_signature_compatible(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "out.mp4"
    input_path.write_bytes(b"video")
    configs = load_runtime_configs(_make_runtime_args(output_dir=str(tmp_path)))
    workflow_section = configs.json_section("workflow")
    workflow_config = {
        **workflow_section,
        "interpolation": {**workflow_section["interpolation"], "multi": 3},
    }
    updated = configs.with_workflow(WorkflowConfig.model_validate(workflow_config))
    processing_steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3, "model_version": "4.25", "scale": 1.0, "fp16": False},
            stage_name="01_frame_interpolation",
        )
    ]
    video_info = VideoMetadata(
        width=1280,
        height=720,
        source_fps=30.0,
        source_frames=60,
        duration=2.0,
        has_audio=True,
    )
    sections = updated.json_sections()

    section_signature = build_run_identity(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=sections["workflow"],
        output_config=sections["output"],
        processing_steps=processing_steps,
        video_info=video_info,
    ).signature
    mapping_signature = build_run_identity(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=workflow_config,
        output_config=sections["output"],
        processing_steps=processing_steps,
        video_info=video_info,
    ).signature

    assert updated.workflow.interpolation.multi == 3
    assert section_signature == mapping_signature


def test_runtime_output_config_includes_segment_frames_and_stdin_override(monkeypatch: pytest.MonkeyPatch):
    default_configs = load_runtime_configs(_make_runtime_args(output_dir="D:/output"))
    override_configs = _load_stdin_configs(
        monkeypatch,
        {"output": {"segmentFrames": 240}},
        output_dir="D:/output",
    )

    assert default_configs.json_section("output")["segmentFrames"] == 1000
    assert override_configs.json_section("output")["segmentFrames"] == 240


def test_runtime_config_emits_complete_defaults_for_explicit_wire_contract(monkeypatch: pytest.MonkeyPatch):
    default_configs = load_runtime_configs(_make_runtime_args(output_dir="D:/output"))
    override_configs = _load_stdin_configs(
        monkeypatch,
        {"decode": {}},
        output_dir="D:/output",
    )

    assert default_configs.json_section("decode")["hwaccelDevice"] is None
    assert override_configs.json_section("decode")["hwaccelDevice"] is None


def test_stage_plan_uses_input_frames_for_format_conversion():
    workflow = _make_workflow_config(
        interpolation={
            "enabled": False,
            "targetFps": 60,
            "multi": 2,
            "model": "4.25",
            "scale": 1.0,
            "fp16": False,
            "tensorBackend": "pytorch",
        },
        superResolution={"enabled": False, "scaleFactor": 2.0, "algorithm": "placeholder"},
    )
    projection = StageProjection.from_workflow(workflow)

    plan = build_stage_plan(
        projection,
        240,
        source_duration=10.0,
        output_fps=None,
    )

    assert plan.total_encoded_frames == 240


def test_stage_plan_uses_interpolated_output_frames_without_resample():
    workflow = _make_workflow_config()
    projection = StageProjection.from_workflow(workflow)

    plan = build_stage_plan(
        projection,
        240,
        source_duration=10.0,
        output_fps=None,
    )

    assert plan.total_encoded_frames == 479


def test_stage_plan_uses_target_timeline_when_resampling():
    workflow = _make_workflow_config()
    projection = StageProjection.from_workflow(workflow)

    plan = build_stage_plan(
        projection,
        240,
        source_duration=10.0,
        output_fps=60.0,
    )

    assert plan.total_encoded_frames == 600


def test_stage_worker_parser_requires_config_json():
    parser = build_parser()
    args = parser.parse_args(["stage-worker", "--config-json", "stage.json"])

    assert args.command == "stage-worker"
    assert args.config_json == "stage.json"
    assert callable(args.func)


def test_stage_worker_main_runs_logging_and_handler_only(monkeypatch):
    import importlib

    cli_main = importlib.import_module("app.cli.main")
    calls = []

    class _Parser:
        def parse_args(self):
            return SimpleNamespace(command="stage-worker", func=lambda _args: calls.append("func"))

    monkeypatch.setattr(cli_main, "build_parser", lambda: _Parser())
    monkeypatch.setattr(cli_main, "setup_logging", lambda: calls.append("logging"))
    cli_main.main()

    assert calls == ["logging", "func"]


def test_check_reports_consumed_capabilities_and_model_lists(tmp_path, monkeypatch, capsys):
    model_dir = tmp_path / "models"
    (model_dir / "interpolation" / "rife").mkdir(parents=True)
    (model_dir / "super_resolution" / "placeholder").mkdir(parents=True)
    (model_dir / "flownet_v4.25.pkl").write_bytes(b"model")
    (model_dir / "interpolation" / "rife" / "interp.onnx").write_bytes(b"onnx")
    (model_dir / "super_resolution" / "placeholder" / "sr.onnx").write_bytes(b"onnx")

    monkeypatch.setattr("app.cli.commands.check.FFmpegWrapper", _FakeCheckFFmpeg)
    monkeypatch.setattr(
        "app.cli.commands.check.probe_tensor_engines",
        lambda: {"pytorch": [], "paddle": [], "onnx": []},
    )
    gpu_adapters = [{"name": "NVIDIA GeForce RTX 3070 Laptop GPU", "vendor": "nvidia"}]
    _FakeCheckFFmpeg.discovered_gpu_adapters = None
    monkeypatch.setattr("app.cli.commands.check.list_gpu_adapters", lambda: gpu_adapters)
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(model_dir))
    cmd_check(argparse.Namespace())

    payload = json.loads(capsys.readouterr().out.strip())
    assert set(payload) == {
        "type",
        "ffmpeg",
        "gpu",
        "tensorEngines",
        "interpolationAlgorithms",
        "superResolutionAlgorithms",
        "runtimeMode",
    }
    assert set(payload["ffmpeg"]) == {"available", "hwaccels", "encoderProfiles", "decoderProfiles"}
    assert _FakeCheckFFmpeg.discovered_gpu_adapters is gpu_adapters
    assert payload["gpu"] == {"adapters": gpu_adapters}
    assert payload["tensorEngines"]["onnx"] == []
    assert payload["runtimeMode"] == settings.runtime_mode
    assert "onnxModels" not in payload

    rife_alg = next(a for a in payload["interpolationAlgorithms"] if a["name"] == "rife")
    assert set(rife_alg) == {
        "name",
        "family",
        "tensorBackends",
        "models",
        "onnxModels",
        "modelDetails",
        "onnxModelDetails",
        "scaleFactors",
        "fixedScaleFactor",
        "defaultNumFrames",
        "inputFrameMode",
    }
    assert rife_alg["onnxModels"] == ["interp.onnx"]
    assert rife_alg["modelDetails"]
    assert rife_alg["modelDetails"][0]["metrics"]["parameterCount"] is not None
    assert rife_alg["onnxModelDetails"][0]["name"] == "interp.onnx"
    assert rife_alg["onnxModelDetails"][0]["metrics"]["analysisStatus"] == "unknown"
    placeholder_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "placeholder")
    assert placeholder_alg["onnxModels"] == ["sr.onnx"]
    assert placeholder_alg["onnxModelDetails"][0]["name"] == "sr.onnx"
    sr_names = {a["name"] for a in payload["superResolutionAlgorithms"]}
    assert {
        "ppmsvsr",
        "ppmsvsr-large",
        "edvr",
        "basicvsr",
        "iconvsr",
        "basicvsr-plus-plus",
    }.issubset(sr_names)
    ppmsvsr_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "ppmsvsr")
    assert ppmsvsr_alg["tensorBackends"] == ["paddle"]
    assert ppmsvsr_alg["models"] == ["x4"]
    assert ppmsvsr_alg["scaleFactors"] == [4]
    assert ppmsvsr_alg["defaultNumFrames"] == 10
    assert "sequenceMode" not in ppmsvsr_alg
    assert ppmsvsr_alg["inputFrameMode"] == "editable_chunk"
    assert ppmsvsr_alg["modelDetails"][0]["name"] == "x4"
    assert ppmsvsr_alg["modelDetails"][0]["metrics"]["parameterCount"] is not None
    assert ppmsvsr_alg["modelDetails"][0]["metrics"]["runtimeFrameCount"] is None
    assert "weightUrl" not in ppmsvsr_alg
    assert "weightPath" not in ppmsvsr_alg
    assert "weightAvailable" not in ppmsvsr_alg

    edvr_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "edvr")
    assert "sequenceMode" not in edvr_alg
    assert edvr_alg["inputFrameMode"] == "fixed_window"
    assert edvr_alg["defaultNumFrames"] == 5
    assert edvr_alg["modelDetails"][0]["metrics"]["runtimeFrameCount"] == 5
