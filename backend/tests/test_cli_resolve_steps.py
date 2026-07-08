"""Tests for _resolve_processing_steps with preprocess/postprocess filter chains."""

from app.planning import resolve_processing_steps as _resolve_processing_steps


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
        "preprocess": {"enabled": False, "filters": []},
        "postprocess": {"enabled": False, "filters": []},
    }
    workflow.update(overrides)
    return workflow


def test_preprocess_prepended_before_interpolation():
    config = _make_workflow_config(
        preprocess={
            "enabled": True,
            "filters": [{"kind": "scale", "enabled": True, "params": {"mode": "factor", "factor": 0.5}}],
        }
    )
    steps = _resolve_processing_steps(config)
    assert [s.algorithm_type for s in steps] == ["frame_filter_chain", "frame_interpolation"]
    assert steps[0].algorithm_kwargs["filters"][0]["kind"] == "scale"
    assert steps[0].stage_name == "01_preprocess"
    assert steps[1].stage_name == "02_frame_interpolation"


def test_postprocess_appended_after_interpolation():
    config = _make_workflow_config(
        postprocess={
            "enabled": True,
            "filters": [{"kind": "sharpen", "enabled": True, "params": {"amount": 0.5}}],
        }
    )
    steps = _resolve_processing_steps(config)
    assert [s.algorithm_type for s in steps] == ["frame_interpolation", "frame_filter_chain"]
    assert steps[1].algorithm_kwargs["filters"][0]["kind"] == "sharpen"
    assert steps[0].stage_name == "01_frame_interpolation"
    assert steps[1].stage_name == "02_postprocess"


def test_both_pre_and_postprocess():
    config = _make_workflow_config(
        preprocess={
            "enabled": True,
            "filters": [{"kind": "scale", "enabled": True, "params": {}}],
        },
        postprocess={
            "enabled": True,
            "filters": [{"kind": "color", "enabled": True, "params": {}}],
        },
    )
    steps = _resolve_processing_steps(config)
    assert [s.algorithm_type for s in steps] == [
        "frame_filter_chain",
        "frame_interpolation",
        "frame_filter_chain",
    ]
    assert steps[0].stage_name == "01_preprocess"
    assert steps[1].stage_name == "02_frame_interpolation"
    assert steps[2].stage_name == "03_postprocess"


def test_disabled_pre_post_not_included():
    config = _make_workflow_config()
    steps = _resolve_processing_steps(config)
    assert all(s.algorithm_type != "frame_filter_chain" for s in steps)


def test_preprocess_with_super_resolution_combined():
    config = _make_workflow_config(
        processOrder="super_resolution_then_interpolation",
        superResolution={"enabled": True, "scaleFactor": 2.0, "algorithm": "placeholder"},
        preprocess={
            "enabled": True,
            "filters": [{"kind": "scale", "enabled": True, "params": {}}],
        },
    )
    steps = _resolve_processing_steps(config)
    assert [s.algorithm_type for s in steps] == [
        "frame_filter_chain",
        "super_resolution",
        "frame_interpolation",
    ]


def test_postprocess_with_format_conversion():
    config = _make_workflow_config(
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
        postprocess={
            "enabled": True,
            "filters": [{"kind": "scale", "enabled": True, "params": {}}],
        },
    )
    steps = _resolve_processing_steps(config)
    # format_conversion with no interpolation/sr gives empty algorithm_types,
    # postprocess should still be appended
    assert [s.algorithm_type for s in steps] == ["frame_filter_chain"]
    assert steps[0].stage_name == "01_postprocess"
