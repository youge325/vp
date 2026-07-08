"""Parent-side stage-worker process runtime helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import subprocess
import sys
from typing import Any

from app.errors import ProcessError, TaskErrorCode, error_code_to_wire
from app.planning import StagePlan
from app.planning.manifest import ResumeState
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, _queue_put
from app.processing.streaming.stage_worker import STAGE_EVENT_PREFIX, read_rgb_frame, write_rgb_frame
from app.processing.streaming.worker_plans import StageWorkerPlan, boundary_schedule_for_stage_plan
from app.utils.subprocess_utils import hidden_subprocess_kwargs

TENSORRT_LOG_PREFIX = "[VP_TRT]"


@dataclass(slots=True)
class WorkerHandle:
    process: subprocess.Popen[bytes]
    plan: StageWorkerPlan
    stderr_tail: deque[str]


def parse_stage_event_line(line: str) -> dict[str, Any] | None:
    """Parse a structured worker stderr line, ignoring ordinary stderr."""
    if not line.startswith(STAGE_EVENT_PREFIX):
        return None
    payload = line[len(STAGE_EVENT_PREFIX) :].strip()
    event = json.loads(payload)
    if not isinstance(event, dict):
        return None
    return event


def spawn_stage_workers(
    plans: list[StageWorkerPlan],
    *,
    config_dir: Path,
    python_executable: str,
) -> list[WorkerHandle]:
    handles: list[WorkerHandle] = []
    previous_stdout = None
    root = backend_dir()

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


def backend_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def read_worker_stderr(
    handle: WorkerHandle,
    progress_callbacks: list[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
) -> None:
    stderr = handle.process.stderr
    if stderr is None:
        return
    for raw_line in iter(stderr.readline, b""):
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        event = parse_stage_event_line(line)
        if event is None:
            handle.stderr_tail.append(line)
            if TENSORRT_LOG_PREFIX in line:
                print(line, file=sys.stderr, flush=True)
            continue
        if event.get("type") == "progress":
            callback_index = int(event.get("stageIndex") or handle.plan.config.stage_index) - 1
            if 0 <= callback_index < len(progress_callbacks):
                try:
                    progress_callbacks[callback_index](
                        int(event.get("current") or 0),
                        int(event.get("total") or 1),
                        force=bool(event.get("force") or False),
                        heartbeat=bool(event.get("heartbeat") or False),
                    )
                except BaseException as exc:  # pragma: no cover - defensive thread boundary
                    stop_event.set()
                    error_queue.put(exc)
            continue
        if event.get("type") == "error":
            stop_event.set()
            error_queue.put(
                ProcessError(
                    error_code_to_wire(event.get("code") or TaskErrorCode.PROCESS_FAILED.value),
                    str(event.get("message") or "Stage worker failed."),
                    details=dict(event.get("details") or {}),
                )
            )


def write_decoded_frames_to_worker(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    video_info: dict[str, Any],
    start_source_frame: int,
    worker_stdin: Any,
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
    frame_count: int | None = None,
) -> None:
    if worker_stdin is None:
        error_queue.put(RuntimeError("Stage worker stdin is unavailable."))
        stop_event.set()
        return
    reader = None
    try:
        reader = ffmpeg.open_rawvideo_decoder(
            input_path=input_path,
            width=int(video_info["width"]),
            height=int(video_info["height"]),
            decode_config=decode_config,
            start_frame=start_source_frame,
            frame_count=frame_count,
        )
        while not stop_event.is_set():
            frame = reader.read_frame()
            if frame is None:
                break
            write_rgb_frame(worker_stdin, frame, width=int(video_info["width"]), height=int(video_info["height"]))
        worker_stdin.close()
    except BaseException as exc:  # pragma: no cover - thread boundary
        stop_event.set()
        error_queue.put(exc)
        close_pipe(worker_stdin)
    finally:
        if reader is not None:
            try:
                reader.close()
            except BaseException as exc:  # pragma: no cover - close failures are real pipeline failures
                stop_event.set()
                error_queue.put(exc)


def drain_final_worker_output(
    *,
    final_stdout: Any,
    final_plan: StageWorkerPlan,
    stage_plan: StagePlan,
    resume_state: ResumeState,
    source_frames: int,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
    metrics: PipelineMetrics,
) -> None:
    if final_stdout is None:
        stop_event.set()
        error_queue.put(RuntimeError("Final stage worker stdout is unavailable."))
        return

    output_index = int(resume_state.completed_output_frames)
    emitted_count = 0
    boundary_schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=int(resume_state.start_source_frame),
        source_frames=source_frames,
    )
    try:
        while not stop_event.is_set() and emitted_count < final_plan.output_frame_count:
            frame = read_rgb_frame(
                final_stdout,
                width=final_plan.config.output_width,
                height=final_plan.config.output_height,
            )
            if frame is None:
                break
            emitted_count += 1
            _queue_put(encode_queue, EncodedFrame(output_index=output_index, frame=frame), stop_event)
            metrics.set_queue_depth("encode", encode_queue.qsize())
            output_index += 1
            next_source_frame = boundary_schedule.get(emitted_count)
            if next_source_frame is not None:
                _queue_put(encode_queue, SegmentBoundary(next_source_frame=next_source_frame), stop_event)
        if emitted_count != final_plan.output_frame_count and not stop_event.is_set():
            raise RuntimeError(
                "Stage worker output frame count mismatch: "
                f"expected {final_plan.output_frame_count}, got {emitted_count}."
            )
    except BaseException as exc:
        stop_event.set()
        error_queue.put(exc)


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


def close_pipe(pipe: Any) -> None:
    if pipe is None:
        return
    try:
        pipe.close()
    except Exception:
        pass


__all__ = [
    "WorkerHandle",
    "close_pipe",
    "drain_final_worker_output",
    "parse_stage_event_line",
    "read_worker_stderr",
    "spawn_stage_workers",
    "wait_for_workers",
    "write_decoded_frames_to_worker",
]
