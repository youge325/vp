"""CLI processing-step planning tests."""

import argparse
import io
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.catalog.model_metrics import ModelMetricSpec, RuntimeMetricSpec
from app.generated.protocol_constants import NDJSON_LINE_LIMIT_BYTES
from app.generated.contracts import FfmpegInfo, GpuAdapter, GpuVendor, TensorEngines, WorkflowConfig
from app.cli.commands.check import cmd_check
from app.cli.commands._process_execution import _run_format_conversion
from app.cli.commands._process_planning import PreparedRun
from app.cli.commands._process_validation import load_runtime_configs
from app.cli.parser import build_parser
from app.cli.runtime_configs import runtime_config_section, runtime_config_sections, with_workflow
from app.config import settings
from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from app.planning.processing_steps import ProcessingStep
from app.planning.run_identity import build_run_identity
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.utils.onnx_models import OnnxModelCatalog
from tests.support.workflow_configs import make_workflow_config as _make_workflow_config
from tests.support.video_metadata import make_video_metadata


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
        runtime_config_section(configs, "workflow"),
        source_fps=60.0,
    )
    configs = with_workflow(configs, WorkflowConfig.model_validate(resolved_workflow))
    stage_plan = build_stage_plan(
        projection,
        make_video_metadata(60, duration=1.0, source_fps=60.0),
        output_fps=output_fps,
    )
    assert stage_plan.processing_steps == ()
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
        return FfmpegInfo(available=True, hwaccels=[], encoderProfiles=[], decoderProfiles=[])


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

    sections = runtime_config_sections(configs)
    assert sections["decode"]["mode"] == "software"
    assert sections["decode"]["hwaccelDevice"] is None
    assert sections["encode"]["keepAudio"] is True
    assert sections["workflow"]["interpolation"]["tensorBackend"] == "pytorch"
    assert sections["output"]["outputDir"] == "D:/typed-output"


def test_runtime_config_json_sections_are_defensive_copies():
    configs = load_runtime_configs(_make_runtime_args(output_dir="D:/wire-output"))
    sections = runtime_config_sections(configs)

    assert sections["decode"]["decoder"] == "software"
    assert sections["encode"]["rateControl"] == {"mode": "crf", "value": 18}
    assert sections["workflow"]["processOrder"] == "super_resolution_then_interpolation"
    assert sections["output"]["outputDir"] == "D:/wire-output"

    sections["workflow"]["interpolation"]["multi"] = 99
    assert runtime_config_section(configs, "workflow")["interpolation"]["multi"] == 2


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
    assert "Invalid runtime config bundle" in exc_info.value.message


def test_load_runtime_configs_rejects_non_object_stdin_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.cli.commands._process_validation.sys.stdin",
        io.StringIO('{"workflow": []}'),
    )

    with pytest.raises(ProcessError) as exc_info:
        load_runtime_configs(_make_runtime_args(config_stdin=True))

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "workflow" in exc_info.value.message


def test_load_runtime_configs_rejects_unknown_top_level_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.cli.commands._process_validation.sys.stdin",
        io.StringIO('{"workflow": {}, "legacy": {}}'),
    )

    with pytest.raises(ProcessError) as exc_info:
        load_runtime_configs(_make_runtime_args(config_stdin=True))

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "legacy" in exc_info.value.message


def test_runtime_config_wire_rejects_python_field_names(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = runtime_config_sections(load_runtime_configs(_make_runtime_args(output_dir="D:/output")))
    payload["output"]["output_dir"] = payload["output"].pop("outputDir")

    with pytest.raises(ProcessError) as exc_info:
        _load_stdin_configs(monkeypatch, payload, output_dir="D:/output")

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "outputDir" in exc_info.value.message


def test_runtime_config_workflow_update_keeps_signature_compatible(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "out.mp4"
    input_path.write_bytes(b"video")
    configs = load_runtime_configs(_make_runtime_args(output_dir=str(tmp_path)))
    workflow_section = runtime_config_section(configs, "workflow")
    workflow_config = {
        **workflow_section,
        "interpolation": {**workflow_section["interpolation"], "multi": 3},
    }
    updated = with_workflow(configs, WorkflowConfig.model_validate(workflow_config))
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
    sections = runtime_config_sections(updated)

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
    payload = runtime_config_sections(default_configs)
    payload["output"]["segmentFrames"] = 240
    override_configs = _load_stdin_configs(
        monkeypatch,
        payload,
        output_dir="D:/output",
    )

    assert runtime_config_section(default_configs, "output")["segmentFrames"] == 1000
    assert runtime_config_section(override_configs, "output")["segmentFrames"] == 240


def test_runtime_config_rejects_incomplete_explicit_wire_contract(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(ProcessError) as exc_info:
        _load_stdin_configs(
            monkeypatch,
            {"decode": {}},
            output_dir="D:/output",
        )

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "workflow" in exc_info.value.message


def test_runtime_config_accepts_full_bundle_and_rejects_partial_bundle(monkeypatch: pytest.MonkeyPatch):
    default_configs = load_runtime_configs(_make_runtime_args(output_dir="D:/output"))
    full_configs = _load_stdin_configs(
        monkeypatch,
        runtime_config_sections(default_configs),
        output_dir="D:/output",
    )

    with pytest.raises(ProcessError):
        _load_stdin_configs(
            monkeypatch,
            {
                "workflow": {"interpolation": {"multi": 2}},
                "output": {"outputDir": "D:/output"},
            },
            output_dir="D:/output",
        )

    assert runtime_config_sections(full_configs) == runtime_config_sections(default_configs)


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
        make_video_metadata(240, duration=10.0),
        output_fps=None,
    )

    assert plan.total_encoded_frames == 240


def test_stage_plan_uses_interpolated_output_frames_without_resample():
    workflow = _make_workflow_config()
    projection = StageProjection.from_workflow(workflow)

    plan = build_stage_plan(
        projection,
        make_video_metadata(240, duration=10.0),
        output_fps=None,
    )

    assert plan.total_encoded_frames == 479


def test_stage_plan_uses_target_timeline_when_resampling():
    workflow = _make_workflow_config()
    projection = StageProjection.from_workflow(workflow)

    plan = build_stage_plan(
        projection,
        make_video_metadata(240, duration=10.0),
        output_fps=60.0,
    )

    assert plan.total_encoded_frames == 600


def test_stage_worker_parser_requires_config_json():
    parser = build_parser()
    args = parser.parse_args(["stage-worker", "--config-json", "stage.json"])

    assert args.command == "stage-worker"
    assert args.config_json == "stage.json"
    assert args.handler == "stage_worker"


@pytest.mark.parametrize(
    "module",
    [
        "app.cli.parser",
        "app.cli.commands.check",
        "app.catalog.model_metrics",
        "app.planning.manifest",
    ],
)
def test_lightweight_cli_imports_have_no_runtime_or_logging_side_effects(
    module: str,
    tmp_path,
) -> None:
    log_dir = tmp_path / "import-logs"
    script = (
        "import logging, pathlib, sys; "
        "handlers=tuple(logging.getLogger().handlers); "
        f"import {module}; "
        "assert tuple(logging.getLogger().handlers) == handlers; "
        f"assert not pathlib.Path({str(log_dir)!r}).exists(); "
        "blocked=[name for name in sys.modules if name.startswith(('app.processing.', 'app.benchmark'))]; "
        "assert not blocked, blocked"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "VP_LOG_DIR": str(log_dir)},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_stage_worker_main_runs_logging_and_handler_only(monkeypatch):
    import importlib

    cli_main = importlib.import_module("app.cli.main")
    calls = []

    class _Parser:
        def parse_args(self):
            return SimpleNamespace(command="stage-worker", handler="stage_worker")

    monkeypatch.setattr(cli_main, "build_parser", lambda: _Parser())
    monkeypatch.setattr(cli_main, "_load_handler", lambda _name: lambda _args: calls.append("func"))
    monkeypatch.setattr(cli_main, "setup_logging", lambda: calls.append("logging"))
    cli_main.main()

    assert calls == ["logging", "func"]


def test_check_reports_consumed_capabilities_and_model_lists(tmp_path, monkeypatch, capsys):
    model_dir = tmp_path / "models"
    (model_dir / "interpolation" / "rife").mkdir(parents=True)
    (model_dir / "super_resolution" / "placeholder").mkdir(parents=True)
    (model_dir / "super_resolution" / "realesrgan").mkdir(parents=True)
    (model_dir / "super_resolution" / "edvr").mkdir(parents=True)
    (model_dir / "flownet_v4.25.pkl").write_bytes(b"model")
    (model_dir / "interpolation" / "rife" / "interp.onnx").write_bytes(b"onnx")
    (model_dir / "super_resolution" / "placeholder" / "sr.onnx").write_bytes(b"onnx")
    (model_dir / "super_resolution" / "realesrgan" / "x4.onnx").write_bytes(b"onnx")
    (model_dir / "super_resolution" / "edvr" / "collision.onnx").write_bytes(b"onnx")

    monkeypatch.setattr("app.cli.commands.check.is_available", lambda _path: True)
    monkeypatch.setattr(
        "app.cli.commands.check.discover_capabilities",
        lambda _path, adapters: _FakeCheckFFmpeg().discover_capabilities(adapters),
    )
    monkeypatch.setattr(
        "app.cli.commands.check.probe_tensor_engines",
        lambda: TensorEngines(pytorch=[], paddle=[], onnx=[]),
    )
    gpu_adapters = [GpuAdapter(name="NVIDIA GeForce RTX 3070 Laptop GPU", vendor=GpuVendor.NVIDIA)]
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
    assert payload["gpu"] == {"adapters": [adapter.model_dump(by_alias=True, mode="json") for adapter in gpu_adapters]}
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
        "modelLicense",
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
    realesrgan_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "realesrgan")
    assert realesrgan_alg["tensorBackends"] == ["onnx"]
    assert realesrgan_alg["onnxModels"] == ["x4.onnx"]
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
    assert ppmsvsr_alg["modelLicense"] is None
    assert ppmsvsr_alg["defaultNumFrames"] == 10
    assert "sequenceMode" not in ppmsvsr_alg
    assert ppmsvsr_alg["inputFrameMode"] == "editable_chunk"
    assert ppmsvsr_alg["modelDetails"][0]["name"] == "x4"
    assert ppmsvsr_alg["modelDetails"][0]["metrics"]["parameterCount"] is not None
    assert ppmsvsr_alg["modelDetails"][0]["metrics"]["runtimeFrameCount"] is None
    assert "weightUrl" not in ppmsvsr_alg
    assert "weightPath" not in ppmsvsr_alg
    assert "weightAvailable" not in ppmsvsr_alg

    real_rawvsr = {
        algorithm["name"]: algorithm
        for algorithm in payload["superResolutionAlgorithms"]
        if algorithm["family"] == "pytorch_vsr"
    }
    assert set(real_rawvsr) == {
        "real-rawvsr-basicvsr",
        "real-rawvsr-edvr",
        "real-rawvsr-tdan",
        "real-rawvsr-toflow",
    }
    for name, algorithm in real_rawvsr.items():
        assert algorithm["tensorBackends"] == ["pytorch"]
        assert algorithm["scaleFactors"] == [2, 3, 4]
        assert [detail["name"] for detail in algorithm["modelDetails"]] == ["x2", "x3", "x4"]
        assert algorithm["modelLicense"] == {
            "spdxId": "CC-BY-NC-SA-4.0",
            "usage": "non_commercial",
            "sourceUrl": "https://github.com/zmzhang1998/Real-RawVSR",
        }
        if name == "real-rawvsr-basicvsr":
            assert algorithm["inputFrameMode"] == "editable_chunk"
            assert algorithm["defaultNumFrames"] == 10
        else:
            assert algorithm["inputFrameMode"] == "fixed_window"
            assert algorithm["defaultNumFrames"] == 5
            assert all(detail["metrics"]["inputModulo"] == 16 for detail in algorithm["modelDetails"])

    edvr_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "edvr")
    assert "sequenceMode" not in edvr_alg
    assert edvr_alg["inputFrameMode"] == "fixed_window"
    assert edvr_alg["defaultNumFrames"] == 5
    assert edvr_alg["onnxModels"] == []
    assert edvr_alg["modelDetails"][0]["metrics"]["runtimeFrameCount"] == 5


def test_check_bounds_large_discovered_model_diagnostics(monkeypatch, capsys):
    names = [f"rife-{index}.onnx" for index in range(100)]
    details = [
        ModelMetricSpec(
            name=name,
            label=name,
            parameter_count=None,
            parameter_bytes=None,
            runtime=RuntimeMetricSpec(
                gflops_per_megapixel=None,
                activation_bytes_per_megapixel=None,
                runtime_overhead_bytes=None,
                runtime_frame_count=None,
                input_modulo=None,
                analysis_status="partial",
                analysis_notes=tuple(f"node-{note}:" + "x" * 2_000 for note in range(10)),
            ),
        )
        for name in names
    ]
    raw_diagnostic_bytes = sum(
        len(note.encode("utf-8")) for detail in details for note in detail.runtime.analysis_notes
    )
    assert raw_diagnostic_bytes > NDJSON_LINE_LIMIT_BYTES
    catalog = OnnxModelCatalog(
        names={"interpolation": {"rife": names}, "super_resolution": {}},
        details={"interpolation": {"rife": details}, "super_resolution": {}},
    )
    monkeypatch.setattr("app.cli.commands.check.is_available", lambda _path: True)
    monkeypatch.setattr(
        "app.cli.commands.check.discover_capabilities",
        lambda _path, adapters: _FakeCheckFFmpeg().discover_capabilities(adapters),
    )
    monkeypatch.setattr(
        "app.cli.commands.check.probe_tensor_engines",
        lambda: TensorEngines(pytorch=[], paddle=[], onnx=[]),
    )
    monkeypatch.setattr("app.cli.commands.check.list_gpu_adapters", lambda: [])
    monkeypatch.setattr("app.cli.commands.check.scan_onnx_catalog", lambda _root: catalog)

    cmd_check(argparse.Namespace())

    line = capsys.readouterr().out
    payload = json.loads(line)
    rife = payload["interpolationAlgorithms"][0]
    assert rife["onnxModels"] == names
    assert len(rife["onnxModelDetails"]) == len(names)
    projected_notes = rife["onnxModelDetails"][0]["metrics"]["analysisNotes"]
    assert len(projected_notes) == 8
    assert all(len(note.encode("utf-8")) <= 512 for note in projected_notes)
    assert len(line.encode("utf-8")) <= NDJSON_LINE_LIMIT_BYTES
