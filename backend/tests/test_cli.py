"""CLI processing-step planning tests."""

import argparse

import pytest

from app.cli import _default_output_config, _load_json_arg, _resolve_processing_steps, build_parser
from app.config import settings


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
    merged = _load_json_arg('{"segmentFrames": 240}', config)

    assert config["segmentFrames"] == 1000
    assert merged["segmentFrames"] == 240


def test_process_parser_rejects_removed_temp_override_flag():
    parser = build_parser()
    removed_flag = "--temp" + "-dir"

    with pytest.raises(SystemExit):
        parser.parse_args(["process", "--input", "demo.mp4", removed_flag, "D:/temp"])


def test_resource_summary_omits_legacy_temp_override_key():
    removed_key = "_".join(["temp", "dir"])
    assert removed_key not in settings.resource_summary()
