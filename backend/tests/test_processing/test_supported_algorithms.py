"""验证中立 algorithm capability catalog 的完整性。

前端的算法下拉过滤完全依赖该字段:每个算法必须显式声明它在哪些
tensor backend 下有实现。漏声明 = 算法在 UI 上消失;声明错误 = UI 会
出现"切到 paddle 后 RIFE 仍可选,但 spawn 时立即 NotImplementedError"。
本测试在 Python 端把契约钉死,避免上游漂移。
"""

from __future__ import annotations

import pytest
import operator

from app.catalog.algorithm_capabilities import (
    INTERPOLATION_CAPABILITIES,
    SUPER_RESOLUTION_CAPABILITIES,
)
from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS
from app.catalog.model_metrics import MODEL_METRIC_SPECS_BY_ALGORITHM
from app.catalog.rife_models import MODEL_SPECS, SUPPORTED_MODELS
from app.generated.model_assets import REAL_RAWVSR_MODEL_FAMILIES

_VALID_BACKENDS = {"pytorch", "paddle", "onnx"}
_VALID_INPUT_FRAME_MODES = {"none", "editable_chunk", "fixed_window"}
_ALL_CAPABILITIES = (*INTERPOLATION_CAPABILITIES, *SUPER_RESOLUTION_CAPABILITIES)


@pytest.mark.parametrize(
    ("source", "label"),
    [
        (INTERPOLATION_CAPABILITIES, "interpolation"),
        (SUPER_RESOLUTION_CAPABILITIES, "super_resolution"),
    ],
)
def test_every_algorithm_declares_non_empty_tensor_backends(source, label):
    """每个 capability 都必须显式声明 tensor backend。"""
    for entry in source:
        assert entry.descriptor.supported_backends, f"{label} algorithm {entry.name!r} has no tensor backends"


@pytest.mark.parametrize(
    ("source", "label"),
    [
        (INTERPOLATION_CAPABILITIES, "interpolation"),
        (SUPER_RESOLUTION_CAPABILITIES, "super_resolution"),
    ],
)
def test_tensor_backends_values_are_within_known_set(source, label):
    """``tensorBackends`` 里每个字符串都得在 ``{pytorch, paddle, onnx}``。"""
    for entry in source:
        for backend in entry.descriptor.supported_backends:
            assert backend in _VALID_BACKENDS, (
                f"{label} algorithm {entry.name!r} declares unknown backend {backend!r}; "
                f"allowed: {sorted(_VALID_BACKENDS)}"
            )


def test_rife_declares_pytorch_and_onnx_but_not_paddle():
    """RIFE 当前只有 PyTorch 与 ONNX 实现,不应出现在 paddle 下拉中。"""
    rife = next((entry for entry in INTERPOLATION_CAPABILITIES if entry.name == "rife"), None)
    assert rife is not None, "rife missing from interpolation capability catalog"
    backends = set(rife.descriptor.supported_backends)
    assert "pytorch" in backends
    assert "onnx" in backends
    assert "paddle" not in backends, (
        "RIFE declared paddle support but there is no paddle implementation; "
        "this would re-introduce the fixed metadata-contract bug."
    )


def test_builtin_models_expose_metric_details():
    """内置模型必须随算法元数据暴露参数量 / 计算量 / 显存估算基线。"""
    rife = next(entry for entry in INTERPOLATION_CAPABILITIES if entry.name == "rife")
    rife_details = MODEL_METRIC_SPECS_BY_ALGORITHM[rife.name]
    assert len(rife_details) == len(rife.models)
    assert {detail.name for detail in rife_details} == set(rife.models)
    assert all(detail.parameter_count for detail in rife_details)
    assert all(dict(detail.engine_metrics)["tensorrt"] for detail in rife_details)

    paddlegan_entries = [
        entry for entry in SUPER_RESOLUTION_CAPABILITIES if entry.descriptor.supported_backends == frozenset({"paddle"})
    ]
    assert paddlegan_entries
    for entry in paddlegan_entries:
        details = MODEL_METRIC_SPECS_BY_ALGORITHM[entry.name]
        assert details[0].name == "x4"
        assert details[0].parameter_count
        assert dict(details[0].engine_metrics)["tensorrt"]
        assert entry.input_frame_mode in {"editable_chunk", "fixed_window"}


def test_algorithms_expose_ui_capability_metadata():
    """能力 payload 需要携带足够元数据,前端不应再硬编码算法族规则。"""
    rife = next(entry for entry in INTERPOLATION_CAPABILITIES if entry.name == "rife")
    assert rife.descriptor.model_kind == "rife"
    assert rife.input_frame_mode == "none"
    assert rife.descriptor.fixed_scale_factor is None

    onnx_entries = [
        entry for entry in SUPER_RESOLUTION_CAPABILITIES if entry.descriptor.supported_backends == frozenset({"onnx"})
    ]
    assert onnx_entries
    for entry in onnx_entries:
        assert entry.descriptor.model_kind == "onnx_super_resolution"
        assert entry.input_frame_mode == "none"
        assert entry.descriptor.fixed_scale_factor is None

    paddlegan_entries = [
        entry for entry in SUPER_RESOLUTION_CAPABILITIES if entry.descriptor.supported_backends == frozenset({"paddle"})
    ]
    assert paddlegan_entries
    for entry in paddlegan_entries:
        assert entry.descriptor.model_kind == "paddlegan_vsr"
        assert entry.descriptor.fixed_scale_factor == 4
        assert entry.input_frame_mode in _VALID_INPUT_FRAME_MODES
        if entry.name == "edvr":
            assert entry.input_frame_mode == "fixed_window"
        else:
            assert entry.input_frame_mode == "editable_chunk"


def test_paddlegan_window_models_expose_fixed_runtime_frame_count():
    """EDVR 固定使用 5 邻帧窗口,前端不应把它当可编辑帧块数。"""
    edvr = next(entry for entry in SUPER_RESOLUTION_CAPABILITIES if entry.name == "edvr")
    assert edvr.input_frame_mode == "fixed_window"
    assert edvr.default_num_frames == 5
    assert MODEL_METRIC_SPECS_BY_ALGORITHM[edvr.name][0].runtime.runtime_frame_count == 5

    recurrent = [
        entry
        for entry in SUPER_RESOLUTION_CAPABILITIES
        if entry.descriptor.supported_backends == frozenset({"paddle"}) and entry.name != "edvr"
    ]
    assert recurrent
    for entry in recurrent:
        assert entry.input_frame_mode == "editable_chunk"
        assert MODEL_METRIC_SPECS_BY_ALGORITHM[entry.name][0].runtime.runtime_frame_count is None


def test_real_rawvsr_catalog_assets_metrics_factory_and_license_are_exactly_aligned() -> None:
    from app.algorithms.pytorch.real_rawvsr.factory import _IMPLEMENTATION_FACTORIES

    family_ids = {family.algorithm_id for family in REAL_RAWVSR_MODEL_FAMILIES}
    capabilities = {
        entry.name: entry for entry in SUPER_RESOLUTION_CAPABILITIES if entry.descriptor.model_kind == "pytorch_vsr"
    }

    assert family_ids == set(capabilities)
    assert {family.implementation_key for family in REAL_RAWVSR_MODEL_FAMILIES} == set(_IMPLEMENTATION_FACTORIES)
    for family in REAL_RAWVSR_MODEL_FAMILIES:
        capability = capabilities[family.algorithm_id]
        scales = tuple(variant.scale_factor for variant in family.variants)
        assert capability.descriptor.factory_key == "real_rawvsr_rgb"
        assert capability.descriptor.supported_backends == frozenset({"pytorch"})
        assert capability.descriptor.temporal_context_frames == family.temporal_context_frames
        assert capability.scale_factors == scales == (2, 3, 4)
        assert capability.models == tuple(f"x{scale}" for scale in scales)
        assert tuple(metric.name for metric in MODEL_METRIC_SPECS_BY_ALGORITHM[capability.name]) == capability.models
        assert capability.default_num_frames == family.default_num_frames
        assert capability.input_frame_mode == family.input_frame_mode
        assert capability.model_license is not None
        assert capability.model_license.usage == "non_commercial"


def test_catalog_sets_match_model_and_factory_registries() -> None:
    from app.processing.streaming import stage_worker_factory

    rife = next(entry for entry in INTERPOLATION_CAPABILITIES if entry.name == "rife")
    paddle = {entry.name for entry in SUPER_RESOLUTION_CAPABILITIES if entry.descriptor.model_kind == "paddlegan_vsr"}

    assert set(rife.models) == set(SUPPORTED_MODELS)
    assert paddle == set(PADDLEGAN_VSR_SPECS)
    assert set(stage_worker_factory._ALGORITHM_FACTORIES) == {
        entry.descriptor.factory_key for entry in _ALL_CAPABILITIES
    }


def test_model_catalogs_reject_runtime_mutation() -> None:
    with pytest.raises(TypeError):
        operator.setitem(MODEL_SPECS, "future", MODEL_SPECS[SUPPORTED_MODELS[0]])
    with pytest.raises(TypeError):
        operator.setitem(PADDLEGAN_VSR_SPECS, "future", next(iter(PADDLEGAN_VSR_SPECS.values())))
    head_config = MODEL_SPECS["4.7"].head_config
    assert head_config is not None
    with pytest.raises(TypeError):
        operator.setitem(head_config, "in_channels", 99)
