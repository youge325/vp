"""CLI 处理步骤规划测试。"""

from types import SimpleNamespace

from app.cli import _resolve_processing_steps


def _make_args(**overrides):
    defaults = {
        "algorithm": "frame_interpolation",
        "enable_interpolation": False,
        "enable_super_resolution": False,
        "process_order": "super_resolution_then_interpolation",
        "multi": 2,
        "model": "4.25",
        "scale": 1.0,
        "fp16": False,
        "sr_scale_factor": 2.0,
        "sr_algorithm": "placeholder",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_resolve_processing_steps_legacy_algorithm_mode():
    steps = _resolve_processing_steps(_make_args())

    assert [step["algorithm_type"] for step in steps] == ["frame_interpolation"]
    assert steps[0]["algorithm_kwargs"]["multi"] == 2
    assert steps[0]["stage_name"] == "01_frame_interpolation"


def test_resolve_processing_steps_combined_order():
    steps = _resolve_processing_steps(
        _make_args(
            enable_interpolation=True,
            enable_super_resolution=True,
            process_order="frame_interpolation_then_super_resolution",
        )
    )

    assert [step["algorithm_type"] for step in steps] == [
        "frame_interpolation",
        "super_resolution",
    ]
    assert steps[0]["algorithm_kwargs"]["model_version"] == "4.25"
    assert steps[1]["algorithm_kwargs"]["scale_factor"] == 2.0


def test_resolve_processing_steps_format_conversion_skips_frame_filters():
    steps = _resolve_processing_steps(_make_args(algorithm="format_conversion"))

    assert steps == []
