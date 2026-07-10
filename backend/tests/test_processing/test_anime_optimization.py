"""Phase 15 — ``AnimeOptimizationAlgorithm`` 占位实现回归护栏。

当前实现是 no-op 透传(frame in → frame out),正式实现还没落地。本测试
锁住的契约面:

1. ``process_frame`` 不丢帧、不改帧 —— 占位实现以后真正落地算法时,
   这条不变性要先撑住"identity baseline"。
2. ``SUPPORTED_PROFILES`` 是后端 → 前端 capability 探测的硬契约;UI
   下拉列表读这个常量,顺序 / 数量改动等于改协议。锁住 3 个具体值。
3. ``duplicate_threshold`` kwargs 提取(包括默认值)—— 占位实现还没用,
   但调用方已经在传,接口契约不能 silently drift。

这些用例工作量小但都是 fail-loudly 红线 —— 任何一条破了都暗示有人把
占位实现改成了"看似工作但行为偏移"的版本。
"""

from __future__ import annotations

import numpy as np

from app.processing.anime_optimization import (
    SUPPORTED_PROFILES,
    AnimeOptimizationAlgorithm,
)


def test_process_frame_passes_through_unchanged() -> None:
    algorithm = AnimeOptimizationAlgorithm()
    frame = np.full((4, 4, 3), 42, dtype=np.uint8)

    result = algorithm.process_frame(frame)

    # 占位实现必须 identity,不应做任何拷贝 / 类型转换。
    assert result is frame
    assert np.array_equal(result, frame)


def test_supported_profiles_constant_matches_capability_contract() -> None:
    """后端探测 → 前端 Enhance 模块的"动漫优化"下拉,profile 顺序 + 集合
    都是协议级稳定的。改动这里等同于改前端 UI 选项。"""

    assert SUPPORTED_PROFILES == ["clean-lines", "thin-outline", "balanced-cel"]
    # 同时是 list 而非 set,顺序信息也是契约(前端按顺序显示)。
    assert isinstance(SUPPORTED_PROFILES, list)


def test_duplicate_threshold_default_value() -> None:
    algorithm = AnimeOptimizationAlgorithm()

    assert algorithm._duplicate_threshold == 0.996


def test_duplicate_threshold_can_be_overridden_via_kwargs() -> None:
    algorithm = AnimeOptimizationAlgorithm(duplicate_threshold=0.85)

    assert algorithm._duplicate_threshold == 0.85


def test_get_name_remains_stable_for_logging() -> None:
    """``get_name`` 进入 NDJSON ``stage`` 字段,改名等于改前端日志识别。"""

    assert AnimeOptimizationAlgorithm().get_name() == "动漫帧优化算法(占位)"


def test_tensor_backend_kwarg_is_optional_and_stored() -> None:
    """占位实现允许 backend 不存在(实测时 backend 会真的传入,这里只
    检查参数被吸纳,不抛 TypeError)。"""

    class _DummyBackend:
        pass

    backend = _DummyBackend()
    algorithm = AnimeOptimizationAlgorithm(tensor_backend=backend)

    assert algorithm._tensor_backend is backend
