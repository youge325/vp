from __future__ import annotations

from collections import deque
import io
import queue
import threading
from types import SimpleNamespace

import pytest

from app.errors import ProcessError, TaskErrorCode
from app.processing.streaming.error_channel import create_error_queue, report_first_error
from app.processing.streaming.worker_processes import StageWorkerGroup, stage_worker_session
from tests.support.streaming_runtime import ignore_worker_log


def test_stage_worker_session_owns_spawn_stderr_and_cleanup(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    stdin = SimpleNamespace(name="stdin")
    stdout = SimpleNamespace(name="stdout", read=lambda _size: b"")
    handle = SimpleNamespace(
        process=SimpleNamespace(stdin=stdin, stdout=stdout, stderr=None, wait=lambda **_kwargs: 0),
        config=SimpleNamespace(stage_index=2, stage_name="stage-2"),
        stderr_tail=deque(),
    )
    calls: list[tuple[str, object]] = []

    def fake_spawn(plans, *, config_dir):
        calls.append(("spawn", (plans, config_dir.exists())))
        return [handle]

    def fake_stderr(handle_arg, callbacks, _error_queue, _stop_event, worker_log_sink):
        calls.append(("stderr", handle_arg.config.stage_index))
        worker_log_sink("worker line")
        callbacks[1](3, 4)

    monkeypatch.setattr(processes, "_spawn_stage_workers", fake_spawn)
    monkeypatch.setattr(processes, "read_worker_stderr", fake_stderr)
    monkeypatch.setattr(
        processes,
        "close_pipe",
        lambda pipe: calls.append(("close", pipe.name)) if pipe is not None else None,
    )
    monkeypatch.setattr(
        processes,
        "_terminate_and_reap",
        lambda handles, **_kwargs: calls.append(("reap", len(handles))) or (),
    )

    progress: list[tuple[int, int]] = []
    plans = [object()]
    with stage_worker_session(
        plans,
        progress_callbacks=[None, lambda current, total: progress.append((current, total))],
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
        worker_log_sink=ignore_worker_log,
    ) as group:
        assert group.handles == [handle]

    assert calls[0][0] == "spawn"
    assert calls[0][1] == (plans, True)
    assert ("stderr", 2) in calls
    assert ("close", "stdin") in calls
    assert ("close", "stdout") in calls
    assert ("reap", 1) not in calls
    assert progress == [(3, 4)]


def test_stage_worker_success_rejects_extra_output_bytes() -> None:
    handle = SimpleNamespace(
        process=SimpleNamespace(
            stdout=io.BytesIO(b"extra"), stdin=io.BytesIO(), stderr=io.BytesIO(), wait=lambda **_kwargs: 0
        ),
        config=SimpleNamespace(stage_name="stage"),
        stderr_tail=deque(),
    )
    group = StageWorkerGroup([handle], [], [], threading.Event())

    with pytest.raises(RuntimeError, match="more output bytes"):
        group.finish_successfully()


def test_stage_worker_success_rejects_nonzero_exit_with_stderr_context() -> None:
    handle = SimpleNamespace(
        process=SimpleNamespace(stdout=io.BytesIO(), stdin=io.BytesIO(), stderr=io.BytesIO(), wait=lambda **_kwargs: 7),
        config=SimpleNamespace(stage_name="stage"),
        stderr_tail=deque(["late failure"]),
    )
    group = StageWorkerGroup([handle], [], [], threading.Event())

    with pytest.raises(ProcessError, match="non-zero") as exc_info:
        group.finish_successfully()

    assert exc_info.value.details == {"workers": [{"stage": "stage", "return_code": 7, "stderr": ["late failure"]}]}


def test_stage_worker_typed_error_precedes_its_following_nonzero_exit() -> None:
    errors = create_error_queue()
    stop_event = threading.Event()
    typed_error = ProcessError(
        TaskErrorCode.MISSING_MODEL,
        "specific model failure",
        details={"model": "rife"},
    )

    def wait(**_kwargs) -> int:
        report_first_error(errors, stop_event, typed_error)
        return 1

    handle = SimpleNamespace(
        process=SimpleNamespace(stdout=io.BytesIO(), stdin=io.BytesIO(), stderr=io.BytesIO(), wait=wait),
        config=SimpleNamespace(stage_name="rife"),
        stderr_tail=deque(),
    )
    group = StageWorkerGroup([handle], [], [], stop_event, errors)

    with pytest.raises(ProcessError) as exc_info:
        group.finish_successfully()

    assert exc_info.value is typed_error
    assert exc_info.value.code is TaskErrorCode.MISSING_MODEL
    assert exc_info.value.details == {"model": "rife"}


def test_stage_worker_success_reaps_and_rejects_decoder_close_failure() -> None:
    class CloseFailedWriter:
        cleanup_error = OSError("decoder close failed")
        thread_name = "vp-close-failed-writer"
        reaped = False

        def join_until(self, *, deadline: float) -> bool:
            assert deadline >= 0
            return True

        def request_stop(self, *, deadline: float) -> bool:
            assert deadline >= 0
            self.reaped = True
            return True

    writer = CloseFailedWriter()
    group = StageWorkerGroup([], [], [writer], threading.Event())

    with pytest.raises(RuntimeError, match="graceful cleanup") as exc_info:
        group.finish_successfully()

    assert writer.reaped
    assert isinstance(exc_info.value.__cause__, OSError)


def test_stage_worker_session_spawns_with_current_interpreter(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    commands = []

    def fake_popen(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(
            stdin=io.BytesIO(),
            stdout=io.BytesIO(),
            stderr=io.BytesIO(),
            poll=lambda: 0,
            terminate=lambda: None,
            kill=lambda: None,
            wait=lambda **_kwargs: 0,
        )

    config = SimpleNamespace(
        stage_index=1,
        stage_name="01_super_resolution",
        model_dump_json=lambda **_kwargs: '{"stageIndex":1}',
    )
    monkeypatch.setattr(processes.sys, "executable", "python-current")
    monkeypatch.setattr(processes.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(processes, "read_worker_stderr", lambda *_args: None)

    with stage_worker_session(
        [config],
        progress_callbacks=[],
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
        worker_log_sink=ignore_worker_log,
    ):
        pass

    assert commands[0][0] == "python-current"


def test_stage_worker_session_rolls_back_already_started_workers_when_spawn_fails(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    first = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
        poll=lambda: None,
    )
    calls: list[str] = []
    first.terminate = lambda: calls.append("terminate")
    first.kill = lambda: calls.append("kill")
    first.wait = lambda timeout=None: calls.append(f"wait:{timeout}") or 0
    spawn_count = 0

    def fake_popen(_command, **_kwargs):
        nonlocal spawn_count
        spawn_count += 1
        if spawn_count == 2:
            raise OSError("second worker failed")
        return first

    config = SimpleNamespace(stage_index=1, stage_name="stage", model_dump_json=lambda **_kwargs: "{}")
    monkeypatch.setattr(processes.subprocess, "Popen", fake_popen)

    with pytest.raises(OSError, match="second worker failed"):
        with stage_worker_session(
            [config, config],
            progress_callbacks=[],
            error_queue=queue.Queue(),
            stop_event=threading.Event(),
            worker_log_sink=ignore_worker_log,
        ):
            pass

    assert calls[0] == "terminate"
    assert calls[1].startswith("wait:")


def test_stage_worker_session_owns_new_worker_before_closing_previous_stdout(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    class FailingClosePipe(io.BytesIO):
        def close(self) -> None:
            raise OSError("previous stdout close failed")

    cleanup_calls: list[tuple[int, str]] = []
    spawned = []
    for process_id in (1, 2):
        process = SimpleNamespace(
            stdin=io.BytesIO(),
            stdout=FailingClosePipe() if process_id == 1 else io.BytesIO(),
            stderr=io.BytesIO(),
            poll=lambda: None,
            terminate=lambda process_id=process_id: cleanup_calls.append((process_id, "terminate")),
            kill=lambda process_id=process_id: cleanup_calls.append((process_id, "kill")),
            wait=lambda process_id=process_id, **_kwargs: cleanup_calls.append((process_id, "wait")) or 0,
        )
        spawned.append(process)

    config = SimpleNamespace(stage_index=1, stage_name="stage", model_dump_json=lambda **_kwargs: "{}")
    monkeypatch.setattr(processes.subprocess, "Popen", lambda *_args, **_kwargs: spawned.pop(0))

    with pytest.raises(OSError, match="previous stdout close failed"):
        with stage_worker_session(
            [config, config],
            progress_callbacks=[],
            error_queue=queue.Queue(),
            stop_event=threading.Event(),
            worker_log_sink=ignore_worker_log,
        ):
            pass

    assert cleanup_calls.count((1, "terminate")) == 1
    assert cleanup_calls.count((2, "terminate")) == 1
    assert cleanup_calls.count((1, "wait")) == 1
    assert cleanup_calls.count((2, "wait")) == 1


def test_stage_worker_session_kills_worker_that_misses_reap_deadline(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    killed = False

    def wait(**_kwargs):
        if not killed:
            raise processes.subprocess.TimeoutExpired("worker", 5)
        return -9

    process = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
        wait=wait,
        poll=lambda: None,
        terminate=lambda: None,
    )

    def kill():
        nonlocal killed
        killed = True

    process.kill = kill
    config = SimpleNamespace(
        stage_index=1,
        stage_name="stage",
        model_dump_json=lambda **_kwargs: "{}",
    )
    monkeypatch.setattr(processes.subprocess, "Popen", lambda *_args, **_kwargs: process)
    errors: queue.Queue[BaseException] = queue.Queue()

    with pytest.raises(RuntimeError, match="success deadline"):
        with stage_worker_session(
            [config],
            progress_callbacks=[],
            error_queue=errors,
            stop_event=threading.Event(),
            worker_log_sink=ignore_worker_log,
        ):
            pass

    assert killed is True
    assert errors.empty()


def test_stage_worker_session_reaps_reader_after_terminate_wait_budget_is_exhausted(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    process_terminated = threading.Event()
    reader_started = threading.Event()
    reader_threads: list[threading.Thread] = []

    def wait_for_process(*, timeout: float) -> int:
        if process_terminated.is_set():
            return -9
        process_terminated.wait(timeout=timeout)
        raise processes.subprocess.TimeoutExpired("worker", timeout)

    process = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
        poll=lambda: 0 if process_terminated.is_set() else None,
        terminate=lambda: None,
        kill=process_terminated.set,
        wait=wait_for_process,
    )
    handle = SimpleNamespace(
        process=process,
        config=SimpleNamespace(stage_index=1),
    )

    def blocking_reader(*_args) -> None:
        reader_threads.append(threading.current_thread())
        reader_started.set()
        process_terminated.wait(timeout=1)

    monkeypatch.setattr(processes, "_WORKER_REAP_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(processes, "_spawn_stage_workers", lambda *_args, **_kwargs: [handle])
    monkeypatch.setattr(processes, "read_worker_stderr", blocking_reader)

    errors: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()
    with pytest.raises(RuntimeError, match="success deadline"):
        with stage_worker_session(
            [object()],
            progress_callbacks=[],
            error_queue=errors,
            stop_event=stop_event,
            worker_log_sink=ignore_worker_log,
        ):
            assert reader_started.wait(timeout=1)

    assert errors.empty()
    assert process_terminated.is_set()
    assert len(reader_threads) == 1
    assert reader_threads[0].daemon is False
    assert reader_threads[0].is_alive() is False
    assert not any(thread.name.startswith("vp-stage-worker-stderr-") for thread in threading.enumerate())


def test_stage_worker_start_failure_reaps_processes_and_joins_started_readers(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    stop_event = threading.Event()
    first_reader_exited = threading.Event()
    lifecycle: list[str] = []
    handles = []
    for stage_index in (1, 2):
        process = SimpleNamespace(
            stdin=io.BytesIO(),
            stdout=io.BytesIO(),
            stderr=io.BytesIO(),
            poll=lambda: None,
            terminate=lambda: lifecycle.append("terminate"),
            kill=lambda: lifecycle.append("kill"),
            wait=lambda **_kwargs: lifecycle.append("reap") or 0,
        )
        handles.append(SimpleNamespace(process=process, config=SimpleNamespace(stage_index=stage_index)))

    def waiting_reader(_handle, _callbacks, _errors, reader_stop, _sink) -> None:
        reader_stop.wait(timeout=1)
        first_reader_exited.set()

    original_start = threading.Thread.start

    def fail_second_start(thread: threading.Thread) -> None:
        if thread.name.endswith("-2"):
            raise RuntimeError("reader start failed")
        original_start(thread)

    monkeypatch.setattr(processes, "_spawn_stage_workers", lambda *_args, **_kwargs: handles)
    monkeypatch.setattr(processes, "read_worker_stderr", waiting_reader)
    monkeypatch.setattr(processes.threading.Thread, "start", fail_second_start)

    with pytest.raises(RuntimeError, match="reader start failed"):
        with stage_worker_session(
            [object(), object()],
            progress_callbacks=[],
            error_queue=queue.Queue(),
            stop_event=stop_event,
            worker_log_sink=ignore_worker_log,
        ):
            pass

    assert first_reader_exited.is_set()
    assert lifecycle.count("reap") == 2
    assert not any(thread.name.startswith("vp-stage-worker-stderr-") for thread in threading.enumerate())


def test_reader_start_failure_retains_owner_after_initial_cleanup_timeout(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    release_cleanup = threading.Event()
    first_reader_started = threading.Event()
    handles = []

    def wait(*, timeout: float) -> int:
        if release_cleanup.is_set():
            return -9
        raise processes.subprocess.TimeoutExpired("worker", timeout)

    for stage_index in (1, 2):
        process = SimpleNamespace(
            stdin=io.BytesIO(),
            stdout=io.BytesIO(),
            stderr=io.BytesIO(),
            poll=lambda: -9 if release_cleanup.is_set() else None,
            terminate=lambda: None,
            kill=lambda: None,
            wait=wait,
        )
        handles.append(SimpleNamespace(process=process, config=SimpleNamespace(stage_index=stage_index)))

    def blocked_reader(_handle, _callbacks, _errors, _stop_event, _sink) -> None:
        first_reader_started.set()
        release_cleanup.wait(timeout=1)

    original_start = threading.Thread.start

    def fail_second_start(thread: threading.Thread) -> None:
        if thread.name.endswith("-2"):
            raise RuntimeError("second reader start failed")
        original_start(thread)

    monkeypatch.setattr(processes, "_WORKER_REAP_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(processes, "_spawn_stage_workers", lambda *_args, **_kwargs: handles)
    monkeypatch.setattr(processes, "read_worker_stderr", blocked_reader)
    monkeypatch.setattr(processes.threading.Thread, "start", fail_second_start)

    try:
        with pytest.raises(RuntimeError, match="cleanup failed") as exc_info:
            with stage_worker_session(
                [object(), object()],
                progress_callbacks=[],
                error_queue=queue.Queue(),
                stop_event=threading.Event(),
                worker_log_sink=ignore_worker_log,
            ):
                pass

        assert first_reader_started.is_set()
        assert getattr(exc_info.value, "owner").handles == handles
        assert any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
    finally:
        release_cleanup.set()
        for thread in tuple(threading.enumerate()):
            if thread.name.startswith("vp-late-cleanup-"):
                thread.join(timeout=1)

    assert not any(thread.name.startswith("vp-stage-worker-stderr-") for thread in threading.enumerate())
    assert not any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())


def test_stage_worker_group_owns_writer_and_reaps_before_bounded_thread_join(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    lifecycle: list[str] = []

    class FakeWriter:
        thread_name = "fake-writer"

        def signal_stop(self) -> None:
            lifecycle.append("writer-signal")

        def request_stop(self, *, deadline: float) -> bool:
            assert deadline >= 0
            lifecycle.append("writer-stop")
            return True

        def join_until(self, *, deadline: float) -> bool:
            assert deadline >= 0
            lifecycle.append("writer-join")
            return True

    handle = SimpleNamespace(
        process=SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(), stderr=io.BytesIO()),
        config=SimpleNamespace(stage_index=1),
    )
    group = processes.StageWorkerGroup(
        handles=[handle],
        stderr_threads=[],
        decoded_frame_writers=[FakeWriter()],
        stop_event=threading.Event(),
    )
    monkeypatch.setattr(
        processes,
        "_terminate_and_reap",
        lambda *_args, **_kwargs: lifecycle.append("reap") or (),
    )

    group.close()

    assert lifecycle == ["writer-signal", "reap", "writer-stop", "writer-join"]


def test_stage_worker_cleanup_failure_retains_owner_until_late_cleanup_finishes() -> None:
    import app.processing.streaming.worker_processes as processes

    released = threading.Event()

    class StuckWriter:
        thread_name = "vp-stuck-writer"

        def signal_stop(self) -> None:
            pass

        def request_stop(self, *, deadline: float) -> bool:
            assert deadline >= 0
            return released.is_set()

        def join_until(self, *, deadline: float) -> bool:
            assert deadline >= 0
            return released.is_set()

    group = processes.StageWorkerGroup(
        handles=[],
        stderr_threads=[],
        decoded_frame_writers=[StuckWriter()],
        stop_event=threading.Event(),
    )

    with pytest.raises(RuntimeError, match="cleanup failed") as exc_info:
        group.close()

    assert getattr(exc_info.value, "owner") is group
    try:
        assert any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
    finally:
        released.set()
        for thread in tuple(threading.enumerate()):
            if thread.name.startswith("vp-late-cleanup-"):
                thread.join(timeout=1)
    assert not any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())


def test_partial_spawn_cleanup_is_retained_until_timed_out_process_is_reaped(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    release_process = threading.Event()
    lifecycle: list[str] = []
    spawn_count = 0

    def wait(*, timeout: float) -> int:
        lifecycle.append("wait")
        if not release_process.is_set():
            raise processes.subprocess.TimeoutExpired("worker", timeout)
        lifecycle.append("reaped")
        return -9

    process = SimpleNamespace(
        stdin=io.BytesIO(),
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
        poll=lambda: -9 if release_process.is_set() else None,
        terminate=lambda: lifecycle.append("terminate"),
        kill=lambda: lifecycle.append("kill"),
        wait=wait,
    )

    def popen(*_args, **_kwargs):
        nonlocal spawn_count
        spawn_count += 1
        if spawn_count == 2:
            raise OSError("second worker failed")
        return process

    config = SimpleNamespace(stage_index=1, stage_name="stage", model_dump_json=lambda **_kwargs: "{}")
    monkeypatch.setattr(processes, "_WORKER_REAP_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(processes.subprocess, "Popen", popen)

    with pytest.raises(RuntimeError, match="cleanup failed") as exc_info:
        with stage_worker_session(
            [config, config],
            progress_callbacks=[],
            error_queue=queue.Queue(),
            stop_event=threading.Event(),
            worker_log_sink=ignore_worker_log,
        ):
            pass

    assert getattr(exc_info.value, "owner").handles[0].process is process
    try:
        assert any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
    finally:
        release_process.set()
        for thread in tuple(threading.enumerate()):
            if thread.name.startswith("vp-late-cleanup-"):
                thread.join(timeout=1)
    assert "reaped" in lifecycle
    assert not any(thread.name.startswith("vp-late-cleanup-") for thread in threading.enumerate())
