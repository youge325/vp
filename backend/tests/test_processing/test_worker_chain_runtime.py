from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from app.planning import ProcessingStep, ResumeState, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.worker_chain_runtime import run_worker_chain_runtime
from app.processing.streaming.worker_plans import StageWorkerPlan


def _stage_plan_and_worker_plan() -> tuple[Any, StageWorkerPlan]:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan([step], 3, source_duration=1.0, output_fps=None)
    worker_plan = StageWorkerPlan(
        config=StageWorkerConfig(
            stage=step,
            stage_index=1,
            stage_total=1,
            stage_name="01_super_resolution",
            input_width=1,
            input_height=1,
            output_width=1,
            output_height=1,
            input_frame_count=2,
            tensor_backend_name="onnx",
            output_frame_count=2,
        ),
        output_frame_count=2,
    )
    return stage_plan, worker_plan


def test_worker_chain_runtime_runs_decode_and_drain_inside_worker_session(monkeypatch) -> None:
    import app.processing.streaming.worker_chain_runtime as runtime

    stage_plan, worker_plan = _stage_plan_and_worker_plan()
    stdin = SimpleNamespace(name="stdin")
    stdout = SimpleNamespace(name="stdout")
    handle = SimpleNamespace(
        process=SimpleNamespace(stdin=stdin, stdout=stdout),
        plan=worker_plan,
    )
    calls: list[tuple[str, Any]] = []

    @contextmanager
    def fake_session(plans, **kwargs):
        calls.append(("session", (plans, kwargs["python_executable"])))
        yield [handle]
        calls.append(("session_closed", len(plans)))

    @contextmanager
    def fake_decoded_frame_writer_session(config, **_kwargs):
        calls.append(
            (
                "decode",
                (
                    config.start_source_frame,
                    config.worker_stdin is stdin,
                    config.width,
                    config.height,
                ),
            )
        )
        yield
        calls.append(("decode_join", None))

    def fake_drain_final_worker_output(**kwargs):
        calls.append(
            (
                "drain",
                (
                    kwargs["final_stdout"] is stdout,
                    kwargs["final_plan"] is worker_plan,
                    kwargs["source_frames"],
                ),
            )
        )

    monkeypatch.setattr(runtime, "stage_worker_session", fake_session)
    monkeypatch.setattr(runtime, "decoded_frame_writer_session", fake_decoded_frame_writer_session)
    monkeypatch.setattr(runtime, "drain_final_worker_output", fake_drain_final_worker_output)

    progress_calls: list[tuple[int, int]] = []
    run_worker_chain_runtime(
        ffmpeg=object(),
        input_path="input.mp4",
        decode_config={"mode": "software"},
        plans=[worker_plan],
        stage_plan=stage_plan,
        progress_callbacks=[lambda current, total, **_kwargs: progress_calls.append((current, total))],
        video_info={"source_frames": 3, "width": 1, "height": 1},
        resume_state=ResumeState(start_source_frame=1, completed_output_frames=0, completed_segments=[]),
        encode_queue=queue.Queue(),
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
        metrics=PipelineMetrics(),
        python_executable="python-test",
    )

    assert calls[0][0] == "session"
    assert calls[0][1][0] == [worker_plan]
    assert calls[0][1][1] == "python-test"
    assert ("decode", (1, True, 1, 1)) in calls
    assert ("drain", (True, True, 3)) in calls
    assert ("decode_join", None) in calls
    assert ("session_closed", 1) in calls
    assert progress_calls == []
