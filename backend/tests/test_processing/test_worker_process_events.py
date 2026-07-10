from __future__ import annotations

from collections import deque
import io
import json
import queue
import threading
from types import SimpleNamespace

from app.errors import ProcessError, TaskErrorCode
from app.processing.streaming.worker_process_events import read_worker_stderr


def test_read_worker_stderr_forwards_tensorrt_lifecycle_logs_to_parent_stderr(capsys) -> None:
    trt_line = (
        "22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: "
        "[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x128x128"
    )
    stderr = io.BytesIO(
        (
            f"{trt_line}\n"
            "ordinary worker stderr\n"
            'VP_STAGE_EVENT {"type":"progress","stageIndex":1,"current":1,"total":5}\n'
        ).encode("utf-8")
    )
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    progress_calls: list[tuple[int, int]] = []

    read_worker_stderr(
        handle,
        [lambda current, total, **_kwargs: progress_calls.append((current, total))],
        queue.Queue(),
        threading.Event(),
    )

    captured = capsys.readouterr()
    assert trt_line in captured.err
    assert "ordinary worker stderr" not in captured.err
    assert progress_calls == [(1, 5)]
    assert list(handle.stderr_tail) == [
        trt_line,
        "ordinary worker stderr",
    ]


def test_read_worker_stderr_normalizes_legacy_error_code_string() -> None:
    event = {
        "type": "error",
        "code": "TaskErrorCode.MISSING_MODEL",
        "message": "missing aux weight",
        "details": {"path": "spynet.pdparams"},
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\n".encode("utf-8"))
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], error_queue, stop_event)

    error = error_queue.get_nowait()
    assert isinstance(error, ProcessError)
    assert error.code == TaskErrorCode.MISSING_MODEL.value
    assert error.message == "missing aux weight"
    assert stop_event.is_set()


def test_read_worker_stderr_forwards_second_stage_zero_progress() -> None:
    events = [
        {
            "type": "progress",
            "stageIndex": 1,
            "current": 100,
            "total": 100,
        },
        {
            "type": "progress",
            "stageIndex": 2,
            "current": 0,
            "total": 200,
            "force": True,
            "heartbeat": True,
        },
    ]
    stderr = io.BytesIO("".join(f"VP_STAGE_EVENT {json.dumps(event)}\n" for event in events).encode("utf-8"))
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    progress_calls: list[tuple[int, int, int, bool, bool]] = []
    callbacks = [
        lambda current, total, **kwargs: progress_calls.append(
            (1, current, total, bool(kwargs.get("force")), bool(kwargs.get("heartbeat")))
        ),
        lambda current, total, **kwargs: progress_calls.append(
            (2, current, total, bool(kwargs.get("force")), bool(kwargs.get("heartbeat")))
        ),
    ]

    read_worker_stderr(handle, callbacks, queue.Queue(), threading.Event())

    assert progress_calls == [(1, 100, 100, False, False), (2, 0, 200, True, True)]


def test_read_worker_stderr_skips_empty_progress_callback_slots() -> None:
    events = [
        {
            "type": "progress",
            "stageIndex": 1,
            "current": 10,
            "total": 10,
        },
        {
            "type": "progress",
            "stageIndex": 2,
            "current": 3,
            "total": 5,
        },
    ]
    stderr = io.BytesIO("".join(f"VP_STAGE_EVENT {json.dumps(event)}\n" for event in events).encode("utf-8"))
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    progress_calls: list[tuple[int, int]] = []

    read_worker_stderr(
        handle,
        [None, lambda current, total, **_kwargs: progress_calls.append((current, total))],
        error_queue,
        stop_event,
    )

    assert progress_calls == [(3, 5)]
    assert error_queue.empty()
    assert not stop_event.is_set()
