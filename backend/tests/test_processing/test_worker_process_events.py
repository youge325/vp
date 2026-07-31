from __future__ import annotations

from collections import deque
import io
import json
import queue
import threading
from types import SimpleNamespace

from app.errors import ProcessError
from app.adapters.streaming_runtime import CliWorkerLogSink
from app.generated.protocol_constants import NDJSON_LINE_LIMIT_BYTES
from app.processing.streaming.error_channel import create_error_queue
from app.processing.streaming.worker_process_events import read_worker_stderr
from tests.support.streaming_runtime import ignore_worker_log


def _worker_handle(
    stderr: io.BytesIO,
    *,
    stage_index: int = 1,
    stage_total: int = 1,
    stage_name: str = "stage",
):
    return SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        config=SimpleNamespace(stage_index=stage_index, stage_total=stage_total, stage_name=stage_name),
        stderr_tail=deque(),
    )


def test_read_worker_stderr_forwards_tensorrt_lifecycle_logs_to_parent_stderr(capsys) -> None:
    trt_line = (
        "22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: "
        "[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x128x128"
    )
    stderr = io.BytesIO(
        (
            f"{trt_line}\n"
            "ordinary worker stderr\n"
            'VP_STAGE_EVENT {"type":"progress","stageName":"stage","stageIndex":1,"stageTotal":1,'
            '"current":1,"total":5,"heartbeat":false,"force":false}\n'
        ).encode("utf-8")
    )
    handle = _worker_handle(stderr)
    progress_calls: list[tuple[int, int]] = []

    read_worker_stderr(
        handle,
        [lambda current, total, **_kwargs: progress_calls.append((current, total))],
        queue.Queue(),
        threading.Event(),
        CliWorkerLogSink(),
    )

    captured = capsys.readouterr()
    assert trt_line in captured.err
    assert "ordinary worker stderr" not in captured.err
    assert progress_calls == [(1, 5)]
    assert list(handle.stderr_tail) == [
        trt_line,
        "ordinary worker stderr",
    ]


def test_read_worker_stderr_rejects_unknown_error_code() -> None:
    event = {
        "type": "error",
        "code": "not_a_contract_code",
        "message": "missing aux weight",
        "details": {"path": "spynet.pdparams"},
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\n".encode("utf-8"))
    handle = _worker_handle(stderr)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], error_queue, stop_event, ignore_worker_log)

    error = error_queue.get_nowait()
    assert not isinstance(error, ProcessError)
    assert stop_event.is_set()


def test_read_worker_stderr_maps_typed_error_and_continues_draining() -> None:
    event = {
        "type": "error",
        "code": "process_failed",
        "message": "worker inference failed",
        "details": {"stage": "rife"},
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\ntrailing diagnostic\n".encode("utf-8"))
    handle = _worker_handle(stderr)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], error_queue, stop_event, ignore_worker_log)

    error = error_queue.get_nowait()
    assert isinstance(error, ProcessError)
    assert error.message == "worker inference failed"
    assert error.details == {"stage": "rife"}
    assert stop_event.is_set()
    assert list(handle.stderr_tail) == ["trailing diagnostic"]


def test_read_worker_stderr_forwards_its_second_stage_zero_progress() -> None:
    event = {
        "type": "progress",
        "stageIndex": 2,
        "stageName": "stage-2",
        "stageTotal": 2,
        "current": 0,
        "total": 200,
        "force": True,
        "heartbeat": True,
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\n".encode("utf-8"))
    handle = _worker_handle(stderr, stage_index=2, stage_total=2, stage_name="stage-2")
    progress_calls: list[tuple[int, int, int, bool, bool]] = []
    callbacks = [
        lambda current, total, **kwargs: progress_calls.append(
            (1, current, total, bool(kwargs.get("force")), bool(kwargs.get("heartbeat")))
        ),
        lambda current, total, **kwargs: progress_calls.append(
            (2, current, total, bool(kwargs.get("force")), bool(kwargs.get("heartbeat")))
        ),
    ]

    read_worker_stderr(handle, callbacks, queue.Queue(), threading.Event(), ignore_worker_log)

    assert progress_calls == [(2, 0, 200, True, True)]


def test_read_worker_stderr_skips_empty_progress_callback_slots() -> None:
    event = {
        "type": "progress",
        "stageIndex": 2,
        "stageName": "stage-2",
        "stageTotal": 2,
        "current": 3,
        "total": 5,
        "heartbeat": False,
        "force": False,
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\n".encode("utf-8"))
    handle = _worker_handle(stderr, stage_index=2, stage_total=2, stage_name="stage-2")
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    progress_calls: list[tuple[int, int]] = []

    read_worker_stderr(
        handle,
        [None, lambda current, total, **_kwargs: progress_calls.append((current, total))],
        error_queue,
        stop_event,
        ignore_worker_log,
    )

    assert progress_calls == [(3, 5)]
    assert error_queue.empty()
    assert not stop_event.is_set()


def test_read_worker_stderr_rejects_progress_from_another_stage_and_keeps_draining() -> None:
    event = {
        "type": "progress",
        "stageIndex": 2,
        "stageName": "stage-2",
        "stageTotal": 2,
        "current": 1,
        "total": 5,
        "heartbeat": False,
        "force": False,
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\ntrailing diagnostic\n".encode("utf-8"))
    handle = _worker_handle(stderr, stage_index=1, stage_total=2, stage_name="stage-1")
    errors: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [lambda *_args, **_kwargs: None, None], errors, stop_event, ignore_worker_log)

    assert "identity mismatch" in str(errors.get_nowait())
    assert stop_event.is_set()
    assert list(handle.stderr_tail) == ["trailing diagnostic"]


def test_read_worker_stderr_reports_malformed_structured_event_and_keeps_draining() -> None:
    stderr = io.BytesIO(b'VP_STAGE_EVENT {"type":"progress","current":-1,"total":0}\nordinary tail\n')
    handle = _worker_handle(stderr)
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], error_queue, stop_event, ignore_worker_log)

    assert isinstance(error_queue.get_nowait(), (TypeError, ValueError))
    assert stop_event.is_set()
    assert list(handle.stderr_tail) == ["ordinary tail"]


def test_read_worker_stderr_retains_only_first_malformed_event_and_drains_high_volume_tail() -> None:
    malformed = b'VP_STAGE_EVENT {"type":"progress","current":-1,"total":0}\n'
    stderr = io.BytesIO(malformed * 1_000 + b"ordinary tail\n")
    handle = _worker_handle(stderr)
    error_queue = create_error_queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], error_queue, stop_event, ignore_worker_log)

    assert error_queue.qsize() == 1
    assert isinstance(error_queue.get_nowait(), (TypeError, ValueError))
    assert stderr.tell() == len(stderr.getvalue())
    assert stop_event.is_set()
    assert list(handle.stderr_tail) == ["ordinary tail"]


def test_read_worker_stderr_rejects_python_field_names_and_keeps_draining() -> None:
    stderr = io.BytesIO(
        b'VP_STAGE_EVENT {"type":"progress","stage_name":"stage","stageIndex":1,'
        b'"stageTotal":1,"current":1,"total":1,"heartbeat":false,"force":false}\nordinary tail\n'
    )
    handle = _worker_handle(stderr)
    errors: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], errors, stop_event, ignore_worker_log)

    assert isinstance(errors.get_nowait(), (TypeError, ValueError))
    assert stop_event.is_set()
    assert list(handle.stderr_tail) == ["ordinary tail"]


def test_read_worker_stderr_rejects_oversized_line_and_continues_draining() -> None:
    stderr = io.BytesIO(b"x" * (NDJSON_LINE_LIMIT_BYTES + 1) + b"\nnext line\n")
    handle = _worker_handle(stderr)
    errors: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], errors, stop_event, ignore_worker_log)

    assert "protocol limit" in str(errors.get_nowait())
    assert stop_event.is_set()
    assert list(handle.stderr_tail) == ["next line"]


def test_read_worker_stderr_reports_log_sink_failure_and_keeps_draining() -> None:
    handle = _worker_handle(io.BytesIO(b"first diagnostic\nsecond diagnostic\n"))
    errors: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    sink_calls: list[str] = []

    def fail_once(line: str) -> None:
        sink_calls.append(line)
        if len(sink_calls) == 1:
            raise RuntimeError("log sink unavailable")

    read_worker_stderr(handle, [], errors, stop_event, fail_once)

    assert "log sink unavailable" in str(errors.get_nowait())
    assert stop_event.is_set()
    assert sink_calls == ["first diagnostic", "second diagnostic"]
    assert list(handle.stderr_tail) == ["first diagnostic", "second diagnostic"]


def test_read_worker_stderr_bounds_repeated_log_sink_failures_while_draining() -> None:
    lines = [f"diagnostic-{index}" for index in range(1_000)]
    stderr = io.BytesIO(("\n".join(lines) + "\n").encode())
    handle = _worker_handle(stderr)
    errors = create_error_queue()
    stop_event = threading.Event()
    sink_calls: list[str] = []

    def always_fail(line: str) -> None:
        sink_calls.append(line)
        raise RuntimeError(f"sink rejected {line}")

    read_worker_stderr(handle, [], errors, stop_event, always_fail)

    assert errors.qsize() == 1
    assert "sink rejected diagnostic-0" in str(errors.get_nowait())
    assert sink_calls == lines
    assert stderr.tell() == len(stderr.getvalue())
    assert stop_event.is_set()


def test_read_worker_stderr_reports_pipe_read_failure() -> None:
    class FailingStderr:
        def readline(self, _limit: int) -> bytes:
            raise OSError("worker stderr pipe failed")

    handle = _worker_handle(FailingStderr())
    errors: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], errors, stop_event, ignore_worker_log)

    assert "worker stderr pipe failed" in str(errors.get_nowait())
    assert stop_event.is_set()


def test_read_worker_stderr_tail_is_limited_by_bytes_not_line_count() -> None:
    lines = [f"diagnostic-{index}" for index in range(30)]
    handle = _worker_handle(io.BytesIO(("\n".join(lines) + "\n").encode()))

    read_worker_stderr(handle, [], queue.Queue(), threading.Event(), ignore_worker_log)

    assert list(handle.stderr_tail) == lines
