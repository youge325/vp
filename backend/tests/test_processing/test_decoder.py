"""Phase 15 — ``_decoder_worker`` 独立回归护栏。

虽然 [[test_streaming]] 已经端到端覆盖了 decoder + processor + encoder 三个
worker,本测试单独把 ``_decoder_worker`` 钉死,目的是:

* 把 ``start_source_frame >= source_frames`` 立即终止的边界条件锁住 —— 续传
  路径在已完成的视频上重启时会撞这条分支,只有它能让 decoder 不打开 ffmpeg
  reader。
* 把 ``stop_event`` 中断 / reader 抛异常 的两条 thread-boundary 分支锁住 ——
  上层 cancel / IO failure 都依赖 decoder 在这两个事件下能 graceful 退出并
  把 ``_DECODE_END`` 投递回 decode_queue,否则 processor 会永远阻塞。
"""

from __future__ import annotations

import queue
import threading
from typing import Any

import numpy as np

from app.processing.streaming.decoder import _decoder_worker
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import DecodedFrame, _DECODE_END


class _FakeReader:
    """最小的 ``open_rawvideo_decoder().read_frame()`` 假实现。"""

    def __init__(self, frames: list[np.ndarray]) -> None:
        self._frames = list(frames)
        self._index = 0
        self.closed = False

    def read_frame(self) -> np.ndarray | None:
        if self._index >= len(self._frames):
            return None
        frame = self._frames[self._index]
        self._index += 1
        return frame

    def close(self) -> None:
        self.closed = True


class _ExplodingReader:
    """``read_frame`` 抛异常,验证 thread-boundary 走 error_queue。"""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.closed = False

    def read_frame(self) -> np.ndarray | None:
        raise self._exc

    def close(self) -> None:
        self.closed = True


class _FakeFFmpeg:
    """记录 ``open_rawvideo_decoder`` 的入参,允许在测试里观察 start_frame。"""

    def __init__(self, reader: Any) -> None:
        self._reader = reader
        self.open_calls: list[dict[str, Any]] = []

    def open_rawvideo_decoder(self, **kwargs: Any) -> Any:
        self.open_calls.append(kwargs)
        return self._reader


def _frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def _drain(q: queue.Queue[Any]) -> list[Any]:
    items: list[Any] = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def test_decoder_worker_emits_all_frames_then_decode_end() -> None:
    frames = [_frame(10), _frame(20), _frame(30)]
    reader = _FakeReader(frames)
    ffmpeg = _FakeFFmpeg(reader)
    decode_queue: queue.Queue[Any] = queue.Queue()
    encode_queue: queue.Queue[Any] = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    metrics = PipelineMetrics()

    _decoder_worker(
        ffmpeg=ffmpeg,
        input_path="/fake/in.mp4",
        decode_config={},
        width=1,
        height=1,
        start_source_frame=0,
        source_frames=len(frames),
        decode_queue=decode_queue,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    items = _drain(decode_queue)
    decoded = [item for item in items if isinstance(item, DecodedFrame)]
    end_markers = [item for item in items if item is _DECODE_END]

    assert len(decoded) == 3
    assert [item.source_index for item in decoded] == [0, 1, 2]
    assert len(end_markers) == 1
    # ``_DECODE_END`` 始终在最后投递,否则 processor 会先看到 END 而漏掉真实帧。
    assert items[-1] is _DECODE_END
    assert reader.closed is True
    assert error_queue.empty()
    assert ffmpeg.open_calls[0]["start_frame"] == 0


def test_decoder_worker_skips_open_when_start_frame_at_or_past_end() -> None:
    """Phase D resume — start_source_frame ≥ source_frames 表示该输入已经全
    部解码完成,decoder 不应再 open ffmpeg(浪费 IO),直接投 _DECODE_END。"""

    reader = _FakeReader([_frame(1)])
    ffmpeg = _FakeFFmpeg(reader)
    decode_queue: queue.Queue[Any] = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    metrics = PipelineMetrics()

    _decoder_worker(
        ffmpeg=ffmpeg,
        input_path="/fake/in.mp4",
        decode_config={},
        width=1,
        height=1,
        start_source_frame=5,
        source_frames=5,
        decode_queue=decode_queue,
        encode_queue=queue.Queue(),
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    items = _drain(decode_queue)
    assert items == [_DECODE_END]
    assert ffmpeg.open_calls == []  # 没打开 reader,IO 没浪费
    assert reader.closed is False
    assert error_queue.empty()


def test_decoder_worker_honours_stop_event_mid_loop() -> None:
    """``stop_event`` 在解码循环中被 set,decoder 必须立即停止读取并 close
    reader。注意 normal-path 的 ``_queue_put(_DECODE_END)`` 调用本身也会
    check stop_event,所以 stop 路径下 ``_DECODE_END`` 可能不会被 put —— 这是
    设计:上层 cancel 路径既会 set stop_event 也会自己跳出 processor 循环,
    不依赖 _DECODE_END 流过来。所以本测试只断言"reader 被关 + 提前退出 +
    没异常",不断言队尾 sentinel。"""

    frames = [_frame(1), _frame(2), _frame(3), _frame(4)]

    stop_event = threading.Event()

    class _StoppingReader(_FakeReader):
        """读完第 1 帧后 set stop_event,模拟外部 cancel。"""

        def __init__(self, frames: list[np.ndarray], event: threading.Event) -> None:
            super().__init__(frames)
            self._event = event

        def read_frame(self) -> np.ndarray | None:
            frame = super().read_frame()
            if self._index == 1:
                self._event.set()
            return frame

    stopping_reader = _StoppingReader(frames, stop_event)
    ffmpeg = _FakeFFmpeg(stopping_reader)
    decode_queue: queue.Queue[Any] = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    metrics = PipelineMetrics()

    _decoder_worker(
        ffmpeg=ffmpeg,
        input_path="/fake/in.mp4",
        decode_config={},
        width=1,
        height=1,
        start_source_frame=0,
        source_frames=len(frames),
        decode_queue=decode_queue,
        encode_queue=queue.Queue(),
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    items = _drain(decode_queue)
    decoded = [item for item in items if isinstance(item, DecodedFrame)]
    # 第 1 帧读完后 stop_event 被 set;后续读取应该不再发生,所以总共最多
    # 1-2 个 DecodedFrame(取决于 set 与 while 检查的 race)。
    assert len(decoded) <= 2
    assert stopping_reader.closed is True
    assert error_queue.empty()


def test_decoder_worker_routes_read_exception_to_error_queue() -> None:
    """IO 故障(模拟 ffmpeg pipe 突然关闭)必须:
    1. 被 BaseException catch
    2. 把 stop_event 翻 set,通知 processor/encoder 停摆
    3. 把异常推到 error_queue 给上层处理
    4. 仍然投递 _DECODE_END(nowait 版本,即使 queue 满也不卡死)
    """

    failure = OSError("ffmpeg pipe broken")
    ffmpeg = _FakeFFmpeg(_ExplodingReader(failure))
    decode_queue: queue.Queue[Any] = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    metrics = PipelineMetrics()

    _decoder_worker(
        ffmpeg=ffmpeg,
        input_path="/fake/in.mp4",
        decode_config={},
        width=1,
        height=1,
        start_source_frame=0,
        source_frames=3,
        decode_queue=decode_queue,
        encode_queue=queue.Queue(),
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=metrics,
    )

    assert stop_event.is_set()
    raised = error_queue.get_nowait()
    assert raised is failure
    items = _drain(decode_queue)
    # 出错路径上至少要保证 _DECODE_END 被送出,processor 才不会死等。
    assert _DECODE_END in items
