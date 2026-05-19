"""Multi-step post-chain tensor reuse helper.

Phase 11 — 在 RIFE 后跟超分这类"多步 post 链路"中,原本每个 step 都
独立做 ``numpy_to_tensor → process_frame → tensor_to_numpy``,中间步骤
的 numpy↔tensor 转换是冗余的(GPU 上来回搬运)。``run_tensor_chain``
把首尾各做一次 H2D / D2H,中间只在 tensor 上流转,等价行为下消除冗余拷贝。

故意保持薄:

- 不接管 progress emission;每步完成后调用 ``step_callback(index)``,
  让外部按原节奏触发 NDJSON progress 帧。
- 单步 chain(``len(algorithms) == 1``)行为与 ``_run_single_frame_algorithm``
  等价 —— 同样 1 次 H2D + 1 次 D2H,只是把闭包写得更整齐,可以平滑替换。
- 空 chain 直接返回原 frame,不付任何 GPU 开销。
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np


def run_tensor_chain(
    backend: Any,
    algorithms: Sequence[Any],
    frame: np.ndarray,
    *,
    step_callback: Callable[[int], None] | None = None,
) -> np.ndarray:
    """Apply a chain of algorithms to a frame with a single H2D + D2H pair.

    Args:
        backend: 提供 ``numpy_to_tensor`` / ``tensor_to_numpy`` 的 tensor 后端
            (典型为 ``app.algorithms.tensor_backend.ITensorBackend`` 的实现)。
            链中所有算法必须共享同一个 backend。
        algorithms: 按顺序应用的算法实例列表;每个需实现
            ``process_frame(tensor) -> tensor`` 且接受 ``backend.numpy_to_tensor``
            输出格式的 tensor、返回同格式 tensor。
        frame: 输入 HWC uint8 numpy frame。
        step_callback: 可选 —— 每个 step 的 ``process_frame`` 完成后被同步调用,
            参数为该 step 在 ``algorithms`` 中的索引(0-based)。调用方常用此
            回调触发 per-step progress NDJSON 帧,保持与原循环逐 step emit
            的节奏一致。

    Returns:
        最后一步输出经 ``tensor_to_numpy`` 之后的 numpy frame(HWC uint8)。
        若 ``algorithms`` 为空,**原样返回输入 frame**(不发生 H2D / D2H,
        也不触发任何 callback)。
    """
    if not algorithms:
        return frame
    tensor = backend.numpy_to_tensor(frame)
    for index, algorithm in enumerate(algorithms):
        tensor = algorithm.process_frame(tensor)
        if step_callback is not None:
            step_callback(index)
    return backend.tensor_to_numpy(tensor)


__all__ = ["run_tensor_chain"]
