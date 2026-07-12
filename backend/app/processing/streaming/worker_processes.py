"""Parent-side stage-worker process runtime helpers."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
from typing import Any, Iterator

from app.errors import ProcessError, TaskErrorCode
from app.processing.streaming.worker_process_events import read_worker_stderr
from app.processing.streaming.worker_process_io import close_pipe
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.utils.subprocess_utils import hidden_subprocess_kwargs


@dataclass(slots=True)
class _WorkerHandle:
    process: subprocess.Popen[bytes]
    plan: StageWorkerPlan
    stderr_tail: deque[str]


def _spawn_stage_workers(
    plans: list[StageWorkerPlan],
    *,
    config_dir: Path,
    python_executable: str,
) -> list[_WorkerHandle]:
    handles: list[_WorkerHandle] = []
    previous_stdout = None
    root = _backend_dir()

    for index, plan in enumerate(plans):
        config_path = config_dir / f"stage-{index + 1:02d}.json"
        config_path.write_text(json.dumps(plan.config.to_jsonable(), ensure_ascii=False), encoding="utf-8")
        stdin = subprocess.PIPE if index == 0 else previous_stdout
        process = subprocess.Popen(
            [
                python_executable,
                "-m",
                "app",
                "stage-worker",
                "--config-json",
                str(config_path),
            ],
            cwd=str(root),
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **hidden_subprocess_kwargs(),
        )
        if previous_stdout is not None:
            previous_stdout.close()
        if process.stdout is None:
            raise RuntimeError("Unable to capture stage-worker stdout.")
        handles.append(_WorkerHandle(process=process, plan=plan, stderr_tail=deque(maxlen=20)))
        previous_stdout = process.stdout

    return handles


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def _wait_for_workers(handles: list[_WorkerHandle], error_queue: queue.Queue[BaseException]) -> None:
    for handle in handles:
        return_code = handle.process.wait()
        if return_code == 0:
            continue
        message = "\n".join(handle.stderr_tail) or f"stage-worker exited with code {return_code}"
        error_queue.put(
            ProcessError(
                TaskErrorCode.PROCESS_FAILED,
                message,
                details={
                    "stage": handle.plan.config.stage_name,
                    "returnCode": return_code,
                },
            )
        )


@contextmanager
def stage_worker_session(
    plans: list[StageWorkerPlan],
    *,
    progress_callbacks: list[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
    python_executable: str | None = None,
) -> Iterator[list[_WorkerHandle]]:
    with tempfile.TemporaryDirectory(prefix="vp-stage-workers-") as config_dir:
        handles = _spawn_stage_workers(
            plans,
            config_dir=Path(config_dir),
            python_executable=python_executable or sys.executable,
        )
        stderr_threads = [
            threading.Thread(
                target=read_worker_stderr,
                name=f"vp-stage-worker-stderr-{handle.plan.config.stage_index}",
                args=(handle, progress_callbacks, error_queue, stop_event),
                daemon=True,
            )
            for handle in handles
        ]
        for thread in stderr_threads:
            thread.start()

        try:
            yield handles
        finally:
            for handle in handles:
                close_pipe(handle.process.stdin)
                close_pipe(handle.process.stdout)
            _wait_for_workers(handles, error_queue)
            for thread in stderr_threads:
                thread.join(timeout=1)


__all__ = [
    "stage_worker_session",
]
