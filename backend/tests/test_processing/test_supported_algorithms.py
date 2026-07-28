"""验证 ``SUPPORTED_ALGORITHMS`` 元数据携带的 ``tensorBackends`` 字段。

前端的算法下拉过滤完全依赖该字段:每个算法必须显式声明它在哪些
tensor backend 下有实现。漏声明 = 算法在 UI 上消失;声明错误 = UI 会
出现"切到 paddle 后 RIFE 仍可选,但 spawn 时立即 NotImplementedError"。
本测试在 Python 端把契约钉死,避免上游漂移。
"""

from __future__ import annotations

import pytest

from app.processing.interpolation import SUPPORTED_ALGORITHMS as INTERPOLATION_ALGORITHMS
from app.processing.super_resolution import SUPPORTED_ALGORITHMS as SR_ALGORITHMS

_VALID_BACKENDS = {"pytorch", "paddle", "onnx"}
_VALID_INPUT_FRAME_MODES = {"none", "editable_chunk", "fixed_window"}


@pytest.mark.parametrize(
    ("source", "label"),
    [
        (INTERPOLATION_ALGORITHMS, "interpolation"),
        (SR_ALGORITHMS, "super_resolution"),
    ],
)
def test_every_algorithm_declares_non_empty_tensor_backends(source, label):
    """``SUPPORTED_ALGORITHMS`` 中每一项都必须显式声明 ``tensorBackends``。"""
    for entry in source:
        assert "tensorBackends" in entry, f"{label} algorithm {entry.get('name')!r} missing tensorBackends field"
        backends = entry["tensorBackends"]
        assert isinstance(backends, list) and backends, (
            f"{label} algorithm {entry.get('name')!r} has empty / non-list tensorBackends: {backends!r}"
        )


@pytest.mark.parametrize(
    ("source", "label"),
    [
        (INTERPOLATION_ALGORITHMS, "interpolation"),
        (SR_ALGORITHMS, "super_resolution"),
    ],
)
def test_tensor_backends_values_are_within_known_set(source, label):
    """``tensorBackends`` 里每个字符串都得在 ``{pytorch, paddle, onnx}``。"""
    for entry in source:
        for backend in entry["tensorBackends"]:
            assert backend in _VALID_BACKENDS, (
                f"{label} algorithm {entry['name']!r} declares unknown backend {backend!r}; "
                f"allowed: {sorted(_VALID_BACKENDS)}"
            )


def test_rife_declares_pytorch_and_onnx_but_not_paddle():
    """RIFE 当前只有 PyTorch 与 ONNX 实现,不应出现在 paddle 下拉中。"""
    rife = next((entry for entry in INTERPOLATION_ALGORITHMS if entry["name"] == "rife"), None)
    assert rife is not None, "rife missing from interpolation SUPPORTED_ALGORITHMS"
    backends = set(rife["tensorBackends"])
    assert "pytorch" in backends
    assert "onnx" in backends
    assert "paddle" not in backends, (
        "RIFE declared paddle support but there is no paddle implementation; "
        "this would re-introduce the fixed metadata-contract bug."
    )


def test_builtin_models_expose_metric_details():
    """内置模型必须随算法元数据暴露参数量 / 计算量 / 显存估算基线。"""
    rife = next(entry for entry in INTERPOLATION_ALGORITHMS if entry["name"] == "rife")
    assert len(rife["modelDetails"]) == len(rife["models"])
    assert {detail["name"] for detail in rife["modelDetails"]} == set(rife["models"])
    assert all(detail["metrics"]["parameterCount"] for detail in rife["modelDetails"])
    assert all(detail["metrics"]["engineMetrics"]["tensorrt"] for detail in rife["modelDetails"])

    paddlegan_entries = [entry for entry in SR_ALGORITHMS if entry["tensorBackends"] == ["paddle"]]
    assert paddlegan_entries
    for entry in paddlegan_entries:
        assert entry["modelDetails"][0]["name"] == "x4"
        assert entry["modelDetails"][0]["metrics"]["parameterCount"]
        assert entry["modelDetails"][0]["metrics"]["engineMetrics"]["tensorrt"]
        assert entry["inputFrameMode"] in {"editable_chunk", "fixed_window"}


def test_algorithms_expose_ui_capability_metadata():
    """能力 payload 需要携带足够元数据,前端不应再硬编码算法族规则。"""
    rife = next(entry for entry in INTERPOLATION_ALGORITHMS if entry["name"] == "rife")
    assert rife["family"] == "rife"
    assert rife["inputFrameMode"] == "none"
    assert "fixedScaleFactor" not in rife

    onnx_entries = [entry for entry in SR_ALGORITHMS if entry["tensorBackends"] == ["onnx"]]
    assert onnx_entries
    for entry in onnx_entries:
        assert entry["family"] == "onnx_super_resolution"
        assert entry["inputFrameMode"] == "none"
        assert "fixedScaleFactor" not in entry

    paddlegan_entries = [entry for entry in SR_ALGORITHMS if entry["tensorBackends"] == ["paddle"]]
    assert paddlegan_entries
    for entry in paddlegan_entries:
        assert entry["family"] == "paddlegan_vsr"
        assert entry["fixedScaleFactor"] == 4
        assert entry["inputFrameMode"] in _VALID_INPUT_FRAME_MODES
        if entry["name"] == "edvr":
            assert entry["inputFrameMode"] == "fixed_window"
        else:
            assert entry["inputFrameMode"] == "editable_chunk"


def test_paddlegan_window_models_expose_fixed_runtime_frame_count():
    """EDVR 固定使用 5 邻帧窗口,前端不应把它当可编辑帧块数。"""
    edvr = next(entry for entry in SR_ALGORITHMS if entry["name"] == "edvr")
    assert edvr["inputFrameMode"] == "fixed_window"
    assert edvr["defaultNumFrames"] == 5
    assert edvr["modelDetails"][0]["metrics"]["runtimeFrameCount"] == 5

    recurrent = [entry for entry in SR_ALGORITHMS if entry["tensorBackends"] == ["paddle"] and entry["name"] != "edvr"]
    assert recurrent
    for entry in recurrent:
        assert entry["inputFrameMode"] == "editable_chunk"
        assert entry["modelDetails"][0]["metrics"]["runtimeFrameCount"] is None
