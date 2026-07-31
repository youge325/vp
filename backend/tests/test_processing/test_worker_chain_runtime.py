from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from app.planning.manifest import ResumeState
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.worker_chain_runtime import run_worker_chain_runtime
from app.processing.streaming.stage_worker_config import build_stage_worker_step
from app.processing.streaming.worker_runtime_config import WorkerPipelineRuntimeConfig
from tests.support.streaming_runtime import ignore_worker_log


def _stage_plan_and_worker_config() -> tuple[Any, StageWorkerConfig]:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={
            "scale_factor": 1.0,
            "sr_algorithm": "placeholder",
            "onnx_model": None,
            "engine": "cuda",
            "num_frames": 10,
        },
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan(StageProjection((step,)), 3, source_duration=1.0, output_fps=None)
    worker_config = StageWorkerConfig(
        stage=build_stage_worker_step(step),
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
    )
    return stage_plan, worker_config


def test_worker_chain_runtime_runs_decode_and_drain_inside_worker_session(monkeypatch) -> None:
    import app.processing.streaming.worker_chain_runtime as runtime

    stage_plan, worker_config = _stage_plan_and_worker_config()
    stdin = SimpleNamespace(name="stdin")
    stdout = SimpleNamespace(name="stdout")
    handle = SimpleNamespace(
        process=SimpleNamespace(stdin=stdin, stdout=stdout),
        config=worker_config,
    )
    calls: list[tuple[str, Any]] = []

    class FakeGroup:
        handles = [handle]

        def start_decoded_frame_writer(self, config, **_kwargs):
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

    @contextmanager
    def fake_session(configs, **_kwargs):
        calls.append(("session", configs))
        yield FakeGroup()
        calls.append(("session_closed", len(configs)))

    def fake_drain_final_worker_output(**kwargs):
        calls.append(
            (
                "drain",
                (
                    kwargs["final_stdout"] is stdout,
                    kwargs["final_config"] is worker_config,
                    kwargs["source_frames"],
                ),
            )
        )

    monkeypatch.setattr(runtime, "stage_worker_session", fake_session)
    monkeypatch.setattr(runtime, "drain_final_worker_output", fake_drain_final_worker_output)

    progress_calls: list[tuple[int, int]] = []
    config = WorkerPipelineRuntimeConfig(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path="input.mp4",
        decode_config={"mode": "software"},
        stage_plan=stage_plan,
        progress_callbacks=[lambda current, total, **_kwargs: progress_calls.append((current, total))],
        source_width=1,
        source_height=1,
        source_frames=3,
        resume_state=ResumeState(start_source_frame=1, completed_output_frames=0, completed_segments=[]),
        metrics=PipelineMetrics(),
        worker_log_sink=ignore_worker_log,
    )
    run_worker_chain_runtime(
        config=config,
        configs=[worker_config],
        encode_queue=queue.Queue(),
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )

    assert calls[0] == ("session", [worker_config])
    assert ("decode", (1, True, 1, 1)) in calls
    assert ("drain", (True, True, 3)) in calls
    assert ("session_closed", 1) in calls
    assert progress_calls == []
