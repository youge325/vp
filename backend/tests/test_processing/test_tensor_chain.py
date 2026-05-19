"""Phase 11 — tensor chain helper 单测。

``run_tensor_chain`` 保证多步 post 链路在 GPU 上一路流转,只在首尾各
做一次 H2D / D2H;空 chain 直接返回原 frame。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.processing.streaming._tensor_chain import run_tensor_chain


class _CountingBackend:
    """记录 numpy↔tensor 转换次数的 fake backend。

    tensor 用 dict 包装区分于 numpy(``"tensor"``key 的存在标志一次 H2D)。
    """

    def __init__(self) -> None:
        self.to_tensor_calls = 0
        self.to_numpy_calls = 0

    def numpy_to_tensor(self, frame: np.ndarray) -> dict[str, Any]:
        self.to_tensor_calls += 1
        return {"tensor": frame.copy()}

    def tensor_to_numpy(self, tensor: dict[str, Any]) -> np.ndarray:
        self.to_numpy_calls += 1
        return tensor["tensor"]


class _AddOneAlgorithm:
    """对 tensor 做 +1(uint8 wraparound)。期望接收 dict 形式 tensor。"""

    def process_frame(self, tensor: dict[str, Any]) -> dict[str, Any]:
        return {"tensor": (tensor["tensor"].astype(np.uint16) + 1).clip(0, 255).astype(np.uint8)}


def test_run_tensor_chain_single_h2d_and_d2h_for_multi_step() -> None:
    """4 个算法的链路只触发 1 次 numpy_to_tensor + 1 次 tensor_to_numpy。"""
    backend = _CountingBackend()
    algorithms = [_AddOneAlgorithm() for _ in range(4)]
    frame = np.zeros((2, 2, 3), dtype=np.uint8)

    result = run_tensor_chain(backend, algorithms, frame)

    assert backend.to_tensor_calls == 1
    assert backend.to_numpy_calls == 1
    np.testing.assert_array_equal(result, np.full_like(frame, 4))


def test_run_tensor_chain_empty_returns_frame_without_h2d() -> None:
    """空算法链:不付任何 GPU 开销,直接返回原 frame。"""
    backend = _CountingBackend()
    frame = np.full((2, 2, 3), 7, dtype=np.uint8)

    result = run_tensor_chain(backend, [], frame)

    assert backend.to_tensor_calls == 0
    assert backend.to_numpy_calls == 0
    assert result is frame  # 同一对象,未复制


def test_run_tensor_chain_invokes_step_callback_per_algorithm() -> None:
    """step_callback 在每步 process_frame 完成后按索引顺序触发。"""
    backend = _CountingBackend()
    algorithms = [_AddOneAlgorithm() for _ in range(3)]
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    observed: list[int] = []

    run_tensor_chain(backend, algorithms, frame, step_callback=observed.append)

    assert observed == [0, 1, 2]


def test_run_tensor_chain_no_callback_for_empty_chain() -> None:
    """空 chain 下 step_callback 也不应触发。"""
    backend = _CountingBackend()
    triggered: list[int] = []

    run_tensor_chain(backend, [], np.zeros((1, 1, 3), dtype=np.uint8), step_callback=triggered.append)

    assert triggered == []


def test_run_tensor_chain_single_step_equivalent_to_h2d_process_d2h() -> None:
    """单步 chain 行为等价于 _run_single_frame_algorithm:1 次 H2D + 1 次 D2H。"""
    backend = _CountingBackend()
    frame = np.full((1, 1, 3), 10, dtype=np.uint8)

    result = run_tensor_chain(backend, [_AddOneAlgorithm()], frame)

    assert backend.to_tensor_calls == 1
    assert backend.to_numpy_calls == 1
    np.testing.assert_array_equal(result, np.full_like(frame, 11))
