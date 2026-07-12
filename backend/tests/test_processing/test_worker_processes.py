from __future__ import annotations

import queue
import threading
from types import SimpleNamespace

from app.processing.streaming.worker_processes import stage_worker_session


def test_stage_worker_session_owns_spawn_stderr_and_cleanup(monkeypatch) -> None:
    import app.processing.streaming.worker_processes as processes

    stdin = SimpleNamespace(name="stdin")
    stdout = SimpleNamespace(name="stdout")
    handle = SimpleNamespace(
        process=SimpleNamespace(stdin=stdin, stdout=stdout),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=2)),
    )
    calls: list[tuple[str, object]] = []

    def fake_spawn(plans, *, config_dir, python_executable):
        calls.append(("spawn", (plans, config_dir.exists(), python_executable)))
        return [handle]

    def fake_stderr(handle_arg, callbacks, _error_queue, _stop_event):
        calls.append(("stderr", handle_arg.plan.config.stage_index))
        callbacks[1](3, 4)

    monkeypatch.setattr(processes, "_spawn_stage_workers", fake_spawn)
    monkeypatch.setattr(processes, "read_worker_stderr", fake_stderr)
    monkeypatch.setattr(processes, "close_pipe", lambda pipe: calls.append(("close", pipe.name)))
    monkeypatch.setattr(processes, "_wait_for_workers", lambda handles, _queue: calls.append(("wait", len(handles))))

    progress: list[tuple[int, int]] = []
    plans = [object()]
    with stage_worker_session(
        plans,
        progress_callbacks=[None, lambda current, total: progress.append((current, total))],
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
        python_executable="python-test",
    ) as handles:
        assert handles == [handle]

    assert calls[0][0] == "spawn"
    assert calls[0][1] == (plans, True, "python-test")
    assert ("stderr", 2) in calls
    assert ("close", "stdin") in calls
    assert ("close", "stdout") in calls
    assert ("wait", 1) in calls
    assert progress == [(3, 4)]
