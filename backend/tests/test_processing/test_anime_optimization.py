"""Phase 15 — ``AnimeOptimizationAlgorithm`` 占位实现回归护栏。

当前实现是 no-op 透传(frame in → frame out),正式实现还没落地。本测试
锁住的契约面:

1. ``process_frame`` 不丢帧、不改帧 —— 占位实现以后真正落地算法时,
   这条不变性要先撑住"identity baseline"。
2. ``SUPPORTED_PROFILES`` 是后端 → 前端 capability 探测的硬契约;UI
   下拉列表读这个常量,顺序 / 数量改动等于改协议。锁住 3 个具体值。
3. factory 传入的 backend/profile/threshold kwargs 可以被吸纳,但占位实现不保存
   与行为无关的私有状态。

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


def test_get_name_remains_stable_for_logging() -> None:
    """``get_name`` 进入 NDJSON ``stage`` 字段,改名等于改前端日志识别。"""

    assert AnimeOptimizationAlgorithm().get_name() == "动漫帧优化算法(占位)"


def test_constructor_accepts_stage_kwargs_without_retaining_dead_state() -> None:
    """占位实现吸纳 factory kwargs,但不把尚未使用的值伪装成运行时状态。"""

    class _DummyBackend:
        pass

    algorithm = AnimeOptimizationAlgorithm(
        tensor_backend=_DummyBackend(),
        duplicate_threshold=0.85,
        profile="clean-lines",
    )

    assert vars(algorithm) == {}
