"""Parent-side stage-worker process runtime helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import subprocess

from app.errors import ProcessError, TaskErrorCode
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.utils.subprocess_utils import hidden_subprocess_kwargs


@dataclass(slots=True)
class WorkerHandle:
    process: subprocess.Popen[bytes]
    plan: StageWorkerPlan
    stderr_tail: deque[str]


def spawn_stage_workers(
    plans: list[StageWorkerPlan],
    *,
    config_dir: Path,
    python_executable: str,
) -> list[WorkerHandle]:
    handles: list[WorkerHandle] = []
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
        handles.append(WorkerHandle(process=process, plan=plan, stderr_tail=deque(maxlen=20)))
        previous_stdout = process.stdout

    return handles


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def wait_for_workers(handles: list[WorkerHandle], error_queue: queue.Queue[BaseException]) -> None:
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


__all__ = [
    "WorkerHandle",
    "spawn_stage_workers",
    "wait_for_workers",
]
