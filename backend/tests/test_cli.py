"""CLI processing-step planning tests."""

import argparse
import json
from types import SimpleNamespace

import pytest

from app.cli.commands import _process_validation
from app.cli.commands.check import cmd_check
from app.cli.commands._process_planning import ProcessingPlan
from app.cli.commands._process_validation import load_runtime_configs
from app.cli.parser import build_parser
from app.config import settings
from app.errors import ProcessError, TaskErrorCode
from app.planning import (
    ProcessingStep,
    build_signature,
    normalize_processing_steps,
    processing_steps_to_jsonable,
    resolve_expected_output_frames,
    resolve_processing_steps,
)


class _FakeFFmpeg:
    def __init__(self, *, frame_count: int, duration: float):
        self._frame_count = frame_count
        self._duration = duration

    def get_frame_count(self, _input_path: str) -> int:
        return self._frame_count

    def get_duration(self, _input_path: str) -> float:
        return self._duration


def test_processing_plan_does_not_store_unused_output_directory() -> None:
    assert "output_dir" not in ProcessingPlan.__dataclass_fields__


class _FakeCheckFFmpeg:
    def is_available(self) -> bool:
        return True

    def discover_capabilities(self, _gpu_adapters):
        return {"hwaccels": [], "encoderProfiles": [], "decoderProfiles": []}


def _make_runtime_args(**overrides):
    values = {
        "config_stdin": False,
        "decode_config_json": None,
        "workflow_config_json": None,
        "encode_config_json": None,
        "output_config_json": None,
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


def test_process_validation_config_section_collector_is_private():
    assert not hasattr(_process_validation, "collect_config_sections")


def _make_workflow_config(**overrides):
    workflow = {
        "fpsMode": "target",
        "processOrder": "super_resolution_then_interpolation",
        "interpolation": {
            "enabled": True,
            "targetFps": 60,
            "multi": 2,
            "model": "4.25",
            "scale": 1.0,
            "fp16": False,
            "tensorBackend": "pytorch",
        },
        "superResolution": {
            "enabled": False,
            "scaleFactor": 2.0,
            "algorithm": "placeholder",
        },
    }
    workflow.update(overrides)
    return workflow


def test_resolve_processing_steps_interpolation_mode():
    steps = resolve_processing_steps(_make_workflow_config())

    assert [step.algorithm_type for step in steps] == ["frame_interpolation"]
    assert steps[0].algorithm_kwargs["multi"] == 2
    assert steps[0].stage_name == "01_frame_interpolation"


def test_resolve_processing_steps_combined_order():
    steps = resolve_processing_steps(
        _make_workflow_config(
            processOrder="frame_interpolation_then_super_resolution",
            superResolution={
                "enabled": True,
                "scaleFactor": 2.0,
                "algorithm": "placeholder",
            },
        )
    )

    assert [step.algorithm_type for step in steps] == [
        "frame_interpolation",
        "super_resolution",
    ]
    assert steps[0].algorithm_kwargs["model_version"] == "4.25"
    assert steps[1].algorithm_kwargs["scale_factor"] == 2.0


def test_resolve_processing_steps_format_conversion_skips_frame_filters():
    steps = resolve_processing_steps(
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
    )

    assert steps == []


def test_processing_step_json_shape_matches_legacy_mapping():
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2, "model_version": "4.25"},
        stage_name="01_frame_interpolation",
    )

    assert processing_steps_to_jsonable([step]) == [
        {
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {"multi": 2, "model_version": "4.25"},
            "stage_name": "01_frame_interpolation",
        }
    ]


def test_normalize_processing_steps_accepts_typed_and_legacy_mapping():
    typed = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 2},
        stage_name="01_super_resolution",
    )
    legacy = {
        "algorithm_type": "frame_filter_chain",
        "algorithm_kwargs": {"filters": []},
        "stage_name": "02_postprocess",
    }

    steps = normalize_processing_steps([typed, legacy])

    assert steps[0] is typed
    assert steps[1].algorithm_type == "frame_filter_chain"
    assert steps[1].algorithm_kwargs == {"filters": []}
    assert steps[1].stage_name == "02_postprocess"


def test_typed_processing_steps_keep_signature_compatible_with_legacy_mapping(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "out.mp4"
    input_path.write_bytes(b"video")
    legacy_steps = [
        {
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {"multi": 2, "model_version": "4.25", "scale": 1.0, "fp16": False},
            "stage_name": "01_frame_interpolation",
        }
    ]
    typed_steps = normalize_processing_steps(legacy_steps)
    decode_config = {"mode": "software", "decoder": "software", "options": {}}
    encode_config = {"codec": "libx264", "container": "mp4", "keepAudio": True}
    workflow_config = _make_workflow_config()
    output_config = {"outputDir": str(tmp_path), "openOnComplete": False, "segmentFrames": 1000}
    video_info = {
        "width": 1280,
        "height": 720,
        "source_fps": 30.0,
        "source_frames": 60,
    }

    legacy_signature = build_signature(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=legacy_steps,
        video_info=video_info,
    )
    typed_signature = build_signature(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config=workflow_config,
        output_config=output_config,
        processing_steps=typed_steps,
        video_info=video_info,
    )

    assert typed_signature == legacy_signature


def test_load_runtime_configs_returns_typed_models_and_legacy_shape():
    configs = load_runtime_configs(_make_runtime_args(output_dir="D:/typed-output"))

    assert configs.decode.mode == "software"
    assert configs.workflow.interpolation.tensor_backend == "pytorch"
    assert configs.output.output_dir == "D:/typed-output"

    sections = configs.legacy_sections()
    assert sections["decode"]["mode"] == "software"
    assert "hwaccelDevice" not in sections["decode"]
    assert sections["encode"]["keepAudio"] is True
    assert sections["workflow"]["interpolation"]["tensorBackend"] == "pytorch"
    assert sections["output"]["outputDir"] == "D:/typed-output"


def test_load_runtime_configs_keeps_legacy_sections_interface():
    sections = load_runtime_configs(_make_runtime_args(output_dir="D:/legacy-output")).legacy_sections()

    assert sections["decode"]["decoder"] == "software"
    assert sections["encode"]["rateControl"] == {"mode": "crf", "value": 18}
    assert sections["workflow"]["processOrder"] == "super_resolution_then_interpolation"
    assert sections["output"]["outputDir"] == "D:/legacy-output"


def test_load_runtime_configs_rejects_missing_output_dir():
    with pytest.raises(ProcessError) as exc_info:
        load_runtime_configs(_make_runtime_args(output_dir=None))

    assert exc_info.value.code == TaskErrorCode.INVALID_CONFIG
    assert "outputDir" in exc_info.value.message


def test_runtime_config_workflow_update_keeps_signature_compatible(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "out.mp4"
    input_path.write_bytes(b"video")
    configs = load_runtime_configs(_make_runtime_args(output_dir=str(tmp_path)))
    workflow_config = {
        **configs.workflow_json,
        "interpolation": {**configs.workflow_json["interpolation"], "multi": 3},
    }
    updated = configs.with_workflow_json(workflow_config)
    processing_steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3, "model_version": "4.25", "scale": 1.0, "fp16": False},
            stage_name="01_frame_interpolation",
        )
    ]
    video_info = {
        "width": 1280,
        "height": 720,
        "source_fps": 30.0,
        "source_frames": 60,
    }
    sections = updated.legacy_sections()

    typed_signature = build_signature(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=sections["workflow"],
        output_config=sections["output"],
        processing_steps=processing_steps,
        video_info=video_info,
    )
    legacy_signature = build_signature(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config=sections["decode"],
        encode_config=sections["encode"],
        workflow_config=workflow_config,
        output_config=sections["output"],
        processing_steps=processing_steps,
        video_info=video_info,
    )

    assert updated.workflow.interpolation.multi == 3
    assert typed_signature == legacy_signature


def test_runtime_output_config_includes_segment_frames_and_json_override():
    default_configs = load_runtime_configs(_make_runtime_args(output_dir="D:/output"))
    override_configs = load_runtime_configs(
        _make_runtime_args(output_dir="D:/output", output_config_json='{"segmentFrames": 240}')
    )

    assert default_configs.output_json["segmentFrames"] == 1000
    assert override_configs.output_json["segmentFrames"] == 240


def test_resolve_expected_output_frames_uses_input_frames_for_format_conversion():
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
    processing_steps = resolve_processing_steps(workflow)

    total = resolve_expected_output_frames(
        ffmpeg=_FakeFFmpeg(frame_count=240, duration=10.0),
        input_path="demo.mp4",
        workflow_config=workflow,
        processing_steps=processing_steps,
        final_output_fps=None,
    )

    assert total == 240


def test_resolve_expected_output_frames_uses_interpolated_output_frames_without_resample():
    workflow = _make_workflow_config()
    processing_steps = resolve_processing_steps(workflow)

    total = resolve_expected_output_frames(
        ffmpeg=_FakeFFmpeg(frame_count=240, duration=10.0),
        input_path="demo.mp4",
        workflow_config=workflow,
        processing_steps=processing_steps,
        final_output_fps=None,
    )

    assert total == 479


def test_resolve_expected_output_frames_uses_target_timeline_when_resampling():
    workflow = _make_workflow_config()
    processing_steps = resolve_processing_steps(workflow)

    total = resolve_expected_output_frames(
        ffmpeg=_FakeFFmpeg(frame_count=240, duration=10.0),
        input_path="demo.mp4",
        workflow_config=workflow,
        processing_steps=processing_steps,
        final_output_fps=60.0,
    )

    assert total == 600


def test_process_parser_rejects_removed_temp_override_flag():
    parser = build_parser()
    removed_flag = "--temp" + "-dir"

    with pytest.raises(SystemExit):
        parser.parse_args(["process", "--input", "demo.mp4", removed_flag, "D:/temp"])


def test_process_parser_rejects_removed_anime_algorithm() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["process", "--input", "demo.mp4", "--algorithm", "anime_optimization"])


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
        "app.cli.commands.check._check_pytorch_in_subprocess",
        lambda: {"pytorch_available": False, "supports_cuda": False, "supports_tensorrt": False},
    )
    monkeypatch.setattr("app.cli.commands.check._check_paddle_in_subprocess", lambda: {"paddle_available": False})
    monkeypatch.setattr(
        "app.cli.commands.check._check_onnxruntime_in_subprocess",
        lambda: {"onnx_available": True, "supports_cuda": False, "supports_tensorrt": False},
    )
    monkeypatch.setattr("app.cli.commands.check.list_gpu_adapters", lambda: [])
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(model_dir))
    cmd_check(argparse.Namespace())

    payload = json.loads(capsys.readouterr().out.strip())
    assert set(payload) == {
        "type",
        "ffmpeg",
        "gpu",
        "tensorEngines",
        "backendDeviceSupport",
        "interpolationAlgorithms",
        "superResolutionAlgorithms",
        "runtimeMode",
    }
    assert set(payload["ffmpeg"]) == {"available", "hwaccels", "encoderProfiles", "decoderProfiles"}
    assert payload["gpu"] == {"adapters": []}
    assert payload["tensorEngines"]["onnx"] == []
    assert payload["runtimeMode"] == settings.runtime_mode
    assert "onnxModels" not in payload

    rife_alg = next(a for a in payload["interpolationAlgorithms"] if a["name"] == "rife")
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
    assert ppmsvsr_alg["sequenceMode"] == "recurrent"
    assert ppmsvsr_alg["modelDetails"][0]["name"] == "x4"
    assert ppmsvsr_alg["modelDetails"][0]["metrics"]["parameterCount"] is not None
    assert ppmsvsr_alg["modelDetails"][0]["metrics"]["runtimeFrameCount"] is None
    assert "weightUrl" not in ppmsvsr_alg
    assert "weightPath" not in ppmsvsr_alg
    assert "weightAvailable" not in ppmsvsr_alg

    edvr_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "edvr")
    assert edvr_alg["sequenceMode"] == "window"
    assert edvr_alg["defaultNumFrames"] == 5
    assert edvr_alg["modelDetails"][0]["metrics"]["runtimeFrameCount"] == 5
