"""Parent-side rawvideo worker pipeline helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
from typing import Any

from app.errors import ProcessError, TaskErrorCode
from app.planning import ProcessingStep, StagePlan
from app.planning.manifest import ResumeState
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import (
    EncodedFrame,
    SegmentBoundary,
    StreamEnd,
    _ENCODE_END,
    _queue_put,
    _queue_put_nowait,
)
from app.processing.streaming.stage_worker import (
    STAGE_EVENT_PREFIX,
    StageWorkerConfig,
    read_rgb_frame,
    write_rgb_frame,
)
from app.utils.subprocess_utils import hidden_subprocess_kwargs


@dataclass(frozen=True, slots=True)
class StageWorkerPlan:
    """Parent-side plan for one stage-worker process."""

    config: StageWorkerConfig
    output_frame_count: int


@dataclass(slots=True)
class _WorkerHandle:
    process: subprocess.Popen[bytes]
    plan: StageWorkerPlan
    stderr_tail: deque[str]


def build_stage_worker_plans(
    *,
    stage_plan: StagePlan,
    tensor_backend_name: str,
    source_width: int,
    source_height: int,
    source_frame_count: int,
) -> list[StageWorkerPlan]:
    """Build sequential stage-worker configs from a resolved ``StagePlan``."""
    steps = _ordered_steps(stage_plan)
    plans: list[StageWorkerPlan] = []
    input_width = source_width
    input_height = source_height
    input_frame_count = source_frame_count

    for index, step in enumerate(steps, start=1):
        output_width, output_height = _stage_output_dimensions(
            step,
            input_width=input_width,
            input_height=input_height,
        )
        output_frame_count = _stage_output_frame_count(step, input_frame_count)
        plans.append(
            StageWorkerPlan(
                config=StageWorkerConfig(
                    stage=step,
                    stage_index=index,
                    stage_total=len(steps),
                    stage_name=step.stage_name or step.algorithm_type,
                    input_width=input_width,
                    input_height=input_height,
                    output_width=output_width,
                    output_height=output_height,
                    input_frame_count=input_frame_count,
                    tensor_backend_name=_stage_tensor_backend_name(step, tensor_backend_name),
                ),
                output_frame_count=output_frame_count,
            )
        )
        input_width = output_width
        input_height = output_height
        input_frame_count = output_frame_count

    return plans


def parse_stage_event_line(line: str) -> dict[str, Any] | None:
    """Parse a structured worker stderr line, ignoring ordinary stderr."""
    if not line.startswith(STAGE_EVENT_PREFIX):
        return None
    payload = line[len(STAGE_EVENT_PREFIX) :].strip()
    event = json.loads(payload)
    if not isinstance(event, dict):
        return None
    return event


def run_stage_worker_pipeline(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    stage_plan: StagePlan,
    tensor_backend_name: str,
    progress_callbacks: list[Any],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    metrics: PipelineMetrics,
    python_executable: str | None = None,
) -> None:
    """Run algorithm stages as isolated rawvideo subprocesses.

    The function pushes ``EncodedFrame`` / ``SegmentBoundary`` / ``StreamEnd``
    packets into ``encode_queue`` for the existing encoder worker.
    """
    start_source_frame = int(resume_state.start_source_frame)
    remaining_source_frames = max(int(video_info["source_frames"]) - start_source_frame, 0)
    if remaining_source_frames <= 0:
        _queue_put(encode_queue, StreamEnd(next_source_frame=int(video_info["source_frames"])), stop_event)
        return

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name=tensor_backend_name,
        source_width=int(video_info["width"]),
        source_height=int(video_info["height"]),
        source_frame_count=remaining_source_frames,
    )
    if not plans:
        raise RuntimeError("Worker pipeline requires at least one processing stage.")

    with tempfile.TemporaryDirectory(prefix="vp-stage-workers-") as config_dir:
        handles = _spawn_stage_workers(
            plans,
            config_dir=Path(config_dir),
            python_executable=python_executable or sys.executable,
        )
        stderr_threads = [
            threading.Thread(
                target=_read_worker_stderr,
                name=f"vp-stage-worker-stderr-{handle.plan.config.stage_index}",
                args=(handle, progress_callbacks, error_queue, stop_event),
                daemon=True,
            )
            for handle in handles
        ]
        for thread in stderr_threads:
            thread.start()

        decode_thread = threading.Thread(
            target=_write_decoded_frames_to_worker,
            name="vp-stage-worker-decode-writer",
            kwargs={
                "ffmpeg": ffmpeg,
                "input_path": input_path,
                "decode_config": decode_config,
                "video_info": video_info,
                "start_source_frame": start_source_frame,
                "worker_stdin": handles[0].process.stdin,
                "error_queue": error_queue,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        decode_thread.start()

        try:
            _drain_final_worker_output(
                final_stdout=handles[-1].process.stdout,
                final_plan=plans[-1],
                stage_plan=stage_plan,
                resume_state=resume_state,
                source_frames=int(video_info["source_frames"]),
                encode_queue=encode_queue,
                error_queue=error_queue,
                stop_event=stop_event,
                metrics=metrics,
            )
        finally:
            decode_thread.join()
            for handle in handles:
                _close_pipe(handle.process.stdin)
                _close_pipe(handle.process.stdout)
            _wait_for_workers(handles, error_queue)
            for thread in stderr_threads:
                thread.join(timeout=1)

    if not error_queue.empty():
        _queue_put_nowait(encode_queue, _ENCODE_END)
        return
    _queue_put(encode_queue, StreamEnd(next_source_frame=int(video_info["source_frames"])), stop_event)


def boundary_schedule_for_stage_plan(
    *,
    stage_plan: StagePlan,
    start_source_frame: int,
    source_frames: int,
) -> dict[int, int]:
    """Map emitted-frame counts to ``next_source_frame`` segment boundaries."""
    if start_source_frame >= source_frames:
        return {}
    schedule: dict[int, int] = {}
    if stage_plan.interpolation_step is None:
        for next_source_frame in range(start_source_frame + 1, source_frames):
            emitted_count = next_source_frame - start_source_frame
            schedule[emitted_count] = next_source_frame
        return schedule

    multi = int(stage_plan.interpolation_step.algorithm_kwargs.get("multi") or 2)
    for next_source_frame in range(start_source_frame + 1, source_frames):
        emitted_count = (next_source_frame - start_source_frame) * multi
        schedule[emitted_count] = next_source_frame
    return schedule


def _spawn_stage_workers(
    plans: list[StageWorkerPlan],
    *,
    config_dir: Path,
    python_executable: str,
) -> list[_WorkerHandle]:
    handles: list[_WorkerHandle] = []
    previous_stdout = None
    backend_dir = _backend_dir()

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
            cwd=str(backend_dir),
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


def _read_worker_stderr(
    handle: _WorkerHandle,
    progress_callbacks: list[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
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
            continue
        if event.get("type") == "progress":
            callback_index = int(event.get("stageIndex") or handle.plan.config.stage_index) - 1
            if 0 <= callback_index < len(progress_callbacks):
                try:
                    progress_callbacks[callback_index](int(event.get("current") or 0), int(event.get("total") or 1))
                except BaseException as exc:  # pragma: no cover - defensive thread boundary
                    stop_event.set()
                    error_queue.put(exc)
            continue
        if event.get("type") == "error":
            stop_event.set()
            error_queue.put(
                ProcessError(
                    str(event.get("code") or TaskErrorCode.PROCESS_FAILED.value),
                    str(event.get("message") or "Stage worker failed."),
                    details=dict(event.get("details") or {}),
                )
            )


def _write_decoded_frames_to_worker(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    video_info: dict[str, Any],
    start_source_frame: int,
    worker_stdin: Any,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
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
        _close_pipe(worker_stdin)
    finally:
        if reader is not None:
            try:
                reader.close()
            except BaseException as exc:  # pragma: no cover - close failures are real pipeline failures
                stop_event.set()
                error_queue.put(exc)


def _drain_final_worker_output(
    *,
    final_stdout: Any,
    final_plan: StageWorkerPlan,
    stage_plan: StagePlan,
    resume_state: ResumeState,
    source_frames: int,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
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
        while not stop_event.is_set():
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


def _close_pipe(pipe: Any) -> None:
    if pipe is None:
        return
    try:
        pipe.close()
    except Exception:
        pass


def _ordered_steps(stage_plan: StagePlan) -> list[ProcessingStep]:
    steps = list(stage_plan.pre_steps)
    if stage_plan.interpolation_step is not None:
        steps.append(stage_plan.interpolation_step)
    steps.extend(stage_plan.post_steps)
    return steps


def _stage_tensor_backend_name(step: ProcessingStep, default_backend_name: str) -> str:
    return str(step.algorithm_kwargs.get("tensor_backend") or default_backend_name)


def _stage_output_frame_count(step: ProcessingStep, input_frame_count: int) -> int:
    if step.algorithm_type != "frame_interpolation":
        return input_frame_count
    if input_frame_count < 2:
        return input_frame_count
    multi = int(step.algorithm_kwargs.get("multi") or 2)
    return input_frame_count + (input_frame_count - 1) * (multi - 1)


def _stage_output_dimensions(
    step: ProcessingStep,
    *,
    input_width: int,
    input_height: int,
) -> tuple[int, int]:
    if step.algorithm_type != "super_resolution":
        return input_width, input_height
    if not _super_resolution_changes_dimensions(step):
        return input_width, input_height
    scale_factor = float(step.algorithm_kwargs.get("scale_factor") or 1.0)
    return (
        max(1, int(round(input_width * scale_factor))),
        max(1, int(round(input_height * scale_factor))),
    )


def _super_resolution_changes_dimensions(step: ProcessingStep) -> bool:
    sr_algorithm = str(step.algorithm_kwargs.get("sr_algorithm") or "")
    if step.algorithm_kwargs.get("onnx_model"):
        return True
    try:
        from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS
    except Exception:
        return False
    return sr_algorithm in PADDLEGAN_VSR_SPECS


__all__ = [
    "StageWorkerPlan",
    "boundary_schedule_for_stage_plan",
    "build_stage_worker_plans",
    "parse_stage_event_line",
    "run_stage_worker_pipeline",
]
