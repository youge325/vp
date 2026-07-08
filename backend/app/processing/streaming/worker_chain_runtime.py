"""Parent-side rawvideo stage-worker chain runtime."""

from __future__ import annotations

from pathlib import Path
import queue
import sys
import tempfile
import threading
from typing import Any

from app.planning import StagePlan
from app.planning.manifest import ResumeState
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.processing.streaming.worker_processes import (
    close_pipe,
    drain_final_worker_output,
    read_worker_stderr,
    spawn_stage_workers,
    wait_for_workers,
    write_decoded_frames_to_worker,
)


def run_worker_chain_runtime(
    *,
    ffmpeg: Any,
    input_path: str,
    decode_config: dict[str, Any],
    plans: list[StageWorkerPlan],
    stage_plan: StagePlan,
    progress_callbacks: list[Any],
    video_info: dict[str, Any],
    resume_state: ResumeState,
    encode_queue: queue.Queue[Any],
    error_queue: queue.Queue[BaseException],
    stop_event: Any,
    metrics: PipelineMetrics,
    python_executable: str | None = None,
) -> None:
    start_source_frame = int(resume_state.start_source_frame)
    with tempfile.TemporaryDirectory(prefix="vp-stage-workers-") as config_dir:
        handles = spawn_stage_workers(
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

        decode_thread = threading.Thread(
            target=write_decoded_frames_to_worker,
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
            drain_final_worker_output(
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
                close_pipe(handle.process.stdin)
                close_pipe(handle.process.stdout)
            wait_for_workers(handles, error_queue)
            for thread in stderr_threads:
                thread.join(timeout=1)


__all__ = ["run_worker_chain_runtime"]
