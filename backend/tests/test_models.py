"""Pydantic ``OutputConfig`` 必填 validator 回归护栏。

用户要求"强制选择输出目录,不使用默认目录"。Pydantic 是后端单点防御 ——
前端 / Tauri wire / CLI 直调任何路径都最终经过这里,空 / 纯空白都必须
fail-loudly。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import FilterStep, InterpolationConfig, OutputConfig, SuperResolutionConfig


def _kwargs(output_dir: str) -> dict[str, object]:
    return {
        "outputDir": output_dir,
        "openOnComplete": False,
        "segmentFrames": 1000,
    }


def test_output_dir_accepts_valid_absolute_path() -> None:
    cfg = OutputConfig.model_validate(_kwargs("D:/out/clip"))
    assert cfg.output_dir == "D:/out/clip"


def test_output_dir_rejects_empty_string() -> None:
    with pytest.raises(ValidationError):
        OutputConfig.model_validate(_kwargs(""))


def test_output_dir_rejects_whitespace_only() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OutputConfig.model_validate(_kwargs("   \t  "))
    assert "output_dir" in str(exc_info.value)


def test_output_dir_rejects_single_newline() -> None:
    # 换行也属于纯空白,必须被 validator 拒。
    with pytest.raises(ValidationError):
        OutputConfig.model_validate(_kwargs("\n"))


def test_output_dir_accepts_relative_path() -> None:
    # validator 只检查非空,不做语义合法性 / 存在性校验 —— 让 OS 在
    # ``Path(...).mkdir`` 时决定相对路径如何处理。
    cfg = OutputConfig.model_validate(_kwargs("./out"))
    assert cfg.output_dir == "./out"


def test_output_config_rejects_zero_segment_frames() -> None:
    payload = _kwargs("D:/out")
    payload["segmentFrames"] = 0

    with pytest.raises(ValidationError, match="segmentFrames"):
        OutputConfig.model_validate(payload)


def test_filter_step_accepts_anime_cleanup_kind() -> None:
    step = FilterStep.model_validate(
        {
            "kind": "anime_cleanup",
            "enabled": True,
            "params": {"profile": "clean-lines", "denoise": 15, "edgeBoost": 30},
        }
    )

    assert step.kind == "anime_cleanup"


def test_filter_step_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        FilterStep.model_validate({"kind": "anime_optimization", "enabled": True, "params": {}})


def _interpolation_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": True,
        "targetFps": 60.0,
        "multi": 2,
        "algorithm": "rife",
        "model": "4.25",
        "onnxModel": None,
        "scale": 1.0,
        "fp16": False,
        "tensorBackend": "pytorch",
        "engine": "cuda",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"targetFps": 0.0},
        {"multi": 0},
        {"multi": 1},
        {"scale": 0.0},
    ],
)
def test_interpolation_config_rejects_non_processing_values(invalid_field: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        InterpolationConfig.model_validate(_interpolation_kwargs(**invalid_field))


def _super_resolution_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": True,
        "scaleFactor": 2.0,
        "algorithm": "real-esrgan",
        "onnxModel": None,
        "tensorBackend": "onnx",
        "engine": "cuda",
        "numFrames": 1,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"scaleFactor": 0.0},
        {"numFrames": 0},
    ],
)
def test_super_resolution_config_rejects_non_processing_values(invalid_field: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SuperResolutionConfig.model_validate(_super_resolution_kwargs(**invalid_field))
