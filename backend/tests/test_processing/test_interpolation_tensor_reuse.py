"""Phase 11 — interpolation 路径的 prev_tensor 复用回归护栏。

原来 ``_process_interpolated_stream`` 对每对相邻源帧都做两次
``numpy_to_tensor``(prev + current),但 prev 实际就是上一轮的 current,
H2D 拷贝被重复了。本测试用计数 backend 把这条约束钉住:N 个源帧总共
只能调用 ``numpy_to_tensor`` N 次(每帧一次,不多不少)。

测试直接驱动模块级 ``_process_interpolated_stream``,绕过 ffmpeg /
encoder 包装,可独立 / 快速校验内部 tensor 流转。
"""

from __future__ import annotations

import queue
import threading
from typing import Any

import numpy as np

from app.planning import StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.processor import _process_interpolated_stream
from app.processing.streaming.queues import (
    DecodedFrame,
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _DECODE_END,
)


class _CountingBackend:
    """计数版 tensor backend:每次 numpy/tensor 互转都 +1。

    tensor 用 dict 包装,以区分 numpy_to_tensor 是否被多次调用。
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


class _MidpointInterpolation:
    """中点插帧:返回 (prev + current) / 2 的 uint8 平均。"""

    def process_frame_pair(
        self,
        prev_tensor: dict[str, Any],
        current_tensor: dict[str, Any],
        *,
        timestep: float = 0.5,
    ) -> dict[str, Any]:
        del timestep
        prev = prev_tensor["tensor"].astype(np.float32)
        cur = current_tensor["tensor"].astype(np.float32)
        return {"tensor": ((prev + cur) / 2).astype(np.uint8)}


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _drain_encode_queue(encode_queue: queue.Queue[Any]) -> list[Any]:
    items: list[Any] = []
    while not encode_queue.empty():
        items.append(encode_queue.get_nowait())
    return items


def _build_stage_plan(*, multi: int, total_output_frames: int) -> StagePlan:
    return StagePlan(
        pre_steps=[],
        interpolation_step={
            "algorithm_type": "frame_interpolation",
            "algorithm_kwargs": {"multi": multi},
            "stage_name": "interp",
        },
        post_steps=[],
        total_output_frames=total_output_frames,
        total_encoded_frames=total_output_frames,
        total_pairs=max(total_output_frames // multi - 1, 1),
    )


def test_prev_tensor_is_reused_across_consecutive_pairs() -> None:
    """N=4 源帧、multi=2 的纯插值路径:numpy_to_tensor 只能被调用 4 次。

    原实现:每对相邻帧调 2 次 → 2 * (N - 1) = 6 次。
    Phase 11 实现:首帧 lazy + 后续每帧 1 次 → N = 4 次。
    """
    source_count = 4
    multi = 2
    output_total = source_count * multi - (multi - 1)  # 7 = 4 源帧 + 3 中间帧

    backend = _CountingBackend()
    algorithms = {
        "single": [],
        "interpolation": (backend, _MidpointInterpolation()),
        "post": [],
    }
    stage_plan = _build_stage_plan(multi=multi, total_output_frames=output_total)

    decode_queue: queue.Queue[Any] = queue.Queue()
    for source_index in range(source_count):
        decode_queue.put(DecodedFrame(source_index=source_index, frame=_frame((source_index + 1) * 50)))
    decode_queue.put(_DECODE_END)

    encode_queue: queue.Queue[Any] = queue.Queue()
    stop_event = threading.Event()
    metrics = PipelineMetrics()
    progress_calls: list[tuple[int, int]] = []

    _process_interpolated_stream(
        stage_plan=stage_plan,
        algorithms=algorithms,
        progress_callbacks=[lambda current, total: progress_calls.append((current, total))],
        source_frames=source_count,
        resume_output_frames=0,
        decode_queue=decode_queue,
        encode_queue=encode_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    # numpy_to_tensor:首帧 lazy + 后续每帧各 1 次 = source_count
    # (对照原实现的 2 * (source_count - 1) = 6)
    assert backend.to_tensor_calls == source_count, (
        f"prev_tensor 复用失败:expected {source_count} H2D, got {backend.to_tensor_calls}"
    )

    # tensor_to_numpy:每对相邻帧产生 (multi - 1) 个中间帧需 D2H
    # 4 帧 3 对 × 1 中间 = 3
    expected_to_numpy = (source_count - 1) * (multi - 1)
    assert backend.to_numpy_calls == expected_to_numpy

    items = _drain_encode_queue(encode_queue)
    encoded_frames = [item for item in items if isinstance(item, EncodedFrame)]
    boundaries = [item for item in items if isinstance(item, SegmentBoundary)]
    ends = [item for item in items if isinstance(item, StreamEnd)]

    assert len(encoded_frames) == output_total
    assert len(boundaries) == source_count - 1
    assert len(ends) == 1


def test_single_source_frame_does_not_trigger_h2d() -> None:
    """仅 1 个源帧:never 进入插值循环,故首帧的 lazy H2D 也不应触发。"""
    backend = _CountingBackend()
    algorithms = {
        "single": [],
        "interpolation": (backend, _MidpointInterpolation()),
        "post": [],
    }
    stage_plan = _build_stage_plan(multi=2, total_output_frames=1)

    decode_queue: queue.Queue[Any] = queue.Queue()
    decode_queue.put(DecodedFrame(source_index=0, frame=_frame(50)))
    decode_queue.put(_DECODE_END)

    encode_queue: queue.Queue[Any] = queue.Queue()
    stop_event = threading.Event()
    metrics = PipelineMetrics()

    _process_interpolated_stream(
        stage_plan=stage_plan,
        algorithms=algorithms,
        progress_callbacks=[lambda *_: None],
        source_frames=1,
        resume_output_frames=0,
        decode_queue=decode_queue,
        encode_queue=encode_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    assert backend.to_tensor_calls == 0, "单源帧路径不应触发 H2D"
    assert backend.to_numpy_calls == 0


def test_higher_multi_does_not_inflate_h2d_count() -> None:
    """multi=4 时,N 源帧仍然只触发 N 次 numpy_to_tensor;中间帧只走 process_frame_pair。"""
    source_count = 3
    multi = 4
    output_total = (source_count - 1) * multi + 1

    backend = _CountingBackend()
    algorithms = {
        "single": [],
        "interpolation": (backend, _MidpointInterpolation()),
        "post": [],
    }
    stage_plan = _build_stage_plan(multi=multi, total_output_frames=output_total)

    decode_queue: queue.Queue[Any] = queue.Queue()
    for source_index in range(source_count):
        decode_queue.put(DecodedFrame(source_index=source_index, frame=_frame((source_index + 1) * 60)))
    decode_queue.put(_DECODE_END)

    encode_queue: queue.Queue[Any] = queue.Queue()
    stop_event = threading.Event()
    metrics = PipelineMetrics()

    _process_interpolated_stream(
        stage_plan=stage_plan,
        algorithms=algorithms,
        progress_callbacks=[lambda *_: None],
        source_frames=source_count,
        resume_output_frames=0,
        decode_queue=decode_queue,
        encode_queue=encode_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    assert backend.to_tensor_calls == source_count
    # 每对相邻帧产生 (multi - 1) 个中间帧 → D2H
    assert backend.to_numpy_calls == (source_count - 1) * (multi - 1)
