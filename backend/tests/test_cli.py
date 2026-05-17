"""CLI processing-step planning tests."""

import argparse
import json

import pytest

from app.cli import build_parser, cmd_check
from app.cli.commands._process_validation import _load_json_arg
from app.cli.defaults import (
    _default_output_config,
    _resolve_expected_output_frames,
    _resolve_processing_steps,
)
from app.config import settings


class _FakeFFmpeg:
    def __init__(self, *, frame_count: int, duration: float):
        self._frame_count = frame_count
        self._duration = duration

    def get_frame_count(self, _input_path: str) -> int:
        return self._frame_count

    def get_duration(self, _input_path: str) -> float:
        return self._duration


class _FakeCheckFFmpeg:
    ffmpeg_path = "ffmpeg"
    ffprobe_path = "ffprobe"

    def is_available(self) -> bool:
        return True

    def get_version(self) -> str:
        return "ffmpeg test"

    def discover_capabilities(self, _gpu_adapters):
        return {"hwaccels": [], "encoderProfiles": [], "decoderProfiles": []}


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
        "anime": {
            "enabled": False,
            "profile": "clean-lines",
            "denoise": 10,
            "edgeBoost": 15,
        },
    }
    workflow.update(overrides)
    return workflow


def test_resolve_processing_steps_interpolation_mode():
    steps = _resolve_processing_steps(_make_workflow_config())

    assert [step["algorithm_type"] for step in steps] == ["frame_interpolation"]
    assert steps[0]["algorithm_kwargs"]["multi"] == 2
    assert steps[0]["stage_name"] == "01_frame_interpolation"


def test_resolve_processing_steps_combined_order():
    steps = _resolve_processing_steps(
        _make_workflow_config(
            processOrder="frame_interpolation_then_super_resolution",
            superResolution={
                "enabled": True,
                "scaleFactor": 2.0,
                "algorithm": "placeholder",
            },
        )
    )

    assert [step["algorithm_type"] for step in steps] == [
        "frame_interpolation",
        "super_resolution",
    ]
    assert steps[0]["algorithm_kwargs"]["model_version"] == "4.25"
    assert steps[1]["algorithm_kwargs"]["scale_factor"] == 2.0


def test_resolve_processing_steps_format_conversion_skips_frame_filters():
    steps = _resolve_processing_steps(
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


def test_default_output_config_includes_segment_frames_and_json_override():
    args = argparse.Namespace(output_dir="D:/output")
    config = _default_output_config(args)
    from app.models import OutputConfig

    merged = _load_json_arg('{"segmentFrames": 240}', config, OutputConfig)

    assert config["segmentFrames"] == 1000
    assert merged["segmentFrames"] == 240


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
    processing_steps = _resolve_processing_steps(workflow)

    total = _resolve_expected_output_frames(
        ffmpeg=_FakeFFmpeg(frame_count=240, duration=10.0),
        input_path="demo.mp4",
        workflow_config=workflow,
        processing_steps=processing_steps,
        final_output_fps=None,
    )

    assert total == 240


def test_resolve_expected_output_frames_uses_interpolated_output_frames_without_resample():
    workflow = _make_workflow_config()
    processing_steps = _resolve_processing_steps(workflow)

    total = _resolve_expected_output_frames(
        ffmpeg=_FakeFFmpeg(frame_count=240, duration=10.0),
        input_path="demo.mp4",
        workflow_config=workflow,
        processing_steps=processing_steps,
        final_output_fps=None,
    )

    assert total == 479


def test_resolve_expected_output_frames_uses_target_timeline_when_resampling():
    workflow = _make_workflow_config()
    processing_steps = _resolve_processing_steps(workflow)

    total = _resolve_expected_output_frames(
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


def test_resource_summary_omits_legacy_temp_override_key():
    removed_key = "_".join(["temp", "dir"])
    assert removed_key not in settings.resource_summary()


def test_check_reports_onnx_runtime_and_model_lists(tmp_path, monkeypatch, capsys):
    model_dir = tmp_path / "models"
    (model_dir / "interpolation" / "rife").mkdir(parents=True)
    (model_dir / "super_resolution" / "placeholder").mkdir(parents=True)
    (model_dir / "flownet_v4.25.pkl").write_bytes(b"model")
    (model_dir / "interpolation" / "rife" / "interp.onnx").write_bytes(b"onnx")
    (model_dir / "super_resolution" / "placeholder" / "sr.onnx").write_bytes(b"onnx")

    monkeypatch.setattr("app.cli.commands.check.FFmpegWrapper", _FakeCheckFFmpeg)
    monkeypatch.setattr(
        "app.cli.commands.check._check_pytorch_in_subprocess",
        lambda: {"pytorch_available": False, "gpu_available": False, "gpu_devices": []},
    )
    monkeypatch.setattr("app.cli.commands.check._check_paddle_in_subprocess", lambda: {"paddle_available": False})
    monkeypatch.setattr(
        "app.cli.commands.check._check_onnxruntime_in_subprocess",
        lambda: {"onnx_available": True, "providers": ["CPUExecutionProvider"]},
    )
    monkeypatch.setattr("app.cli.commands.check.list_gpu_adapters", lambda: [])
    monkeypatch.setattr(settings, "RIFE_MODEL_DIR", str(model_dir))

    cmd_check(argparse.Namespace())

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["tensorBackends"]["onnx"] is True
    assert payload["onnxRuntime"]["providers"] == ["CPUExecutionProvider"]
    assert "onnxModels" not in payload

    rife_alg = next(a for a in payload["interpolationAlgorithms"] if a["name"] == "rife")
    assert rife_alg["onnxModels"] == ["interp.onnx"]
    placeholder_alg = next(a for a in payload["superResolutionAlgorithms"] if a["name"] == "placeholder")
    assert placeholder_alg["onnxModels"] == ["sr.onnx"]
