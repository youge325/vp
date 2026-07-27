from __future__ import annotations

import queue
import threading

import app.processing.streaming.worker_pipeline as worker_pipeline
from app.planning import ProcessingStep, build_stage_plan
from app.planning.manifest import ResumeState
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import StreamEnd, _ENCODE_END
from app.processing.streaming.worker_runtime_config import WorkerPipelineRuntimeConfig


def _runtime_config(stage_plan, *, start_source_frame: int = 0) -> WorkerPipelineRuntimeConfig:
    return WorkerPipelineRuntimeConfig(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path="input.mp4",
        decode_config={"mode": "software"},
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        progress_callbacks=[],
        source_width=1,
        source_height=1,
        source_frames=3,
        resume_state=ResumeState(
            start_source_frame=start_source_frame,
            completed_output_frames=0,
            completed_segments=[],
        ),
        metrics=PipelineMetrics(),
    )


def test_worker_pipeline_delegates_runtime_and_emits_stream_end(monkeypatch) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan([step], 3, source_duration=1.0, output_fps=None)
    encode_queue: queue.Queue = queue.Queue()
    runtime_calls: list[dict] = []

    def fake_runtime(**kwargs):
        runtime_calls.append(kwargs)

    monkeypatch.setattr(worker_pipeline, "run_worker_chain_runtime", fake_runtime)

    config = _runtime_config(stage_plan, start_source_frame=1)
    worker_pipeline.run_stage_worker_pipeline(
        config=config,
        encode_queue=encode_queue,
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )

    assert len(runtime_calls) == 1
    assert runtime_calls[0]["config"] is config
    assert runtime_calls[0]["plans"][0].config.input_frame_count == 2
    item = encode_queue.get_nowait()
    assert isinstance(item, StreamEnd)
    assert item.next_source_frame == 3


def test_worker_pipeline_enqueues_encode_end_when_runtime_reports_error(monkeypatch) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan([step], 3, source_duration=1.0, output_fps=None)
    encode_queue: queue.Queue = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()

    def fake_runtime(**kwargs):
        kwargs["error_queue"].put(RuntimeError("worker failed"))

    monkeypatch.setattr(worker_pipeline, "run_worker_chain_runtime", fake_runtime)

    config = _runtime_config(stage_plan)
    worker_pipeline.run_stage_worker_pipeline(
        config=config,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=threading.Event(),
    )

    assert encode_queue.get_nowait() is _ENCODE_END


def test_worker_pipeline_emits_stream_end_without_starting_workers_when_input_is_complete(monkeypatch) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan([step], 3, source_duration=1.0, output_fps=None)
    encode_queue: queue.Queue = queue.Queue()
    runtime_calls: list[dict] = []
    monkeypatch.setattr(
        worker_pipeline,
        "run_worker_chain_runtime",
        lambda **kwargs: runtime_calls.append(kwargs),
    )
    config = _runtime_config(stage_plan, start_source_frame=3)

    worker_pipeline.run_stage_worker_pipeline(
        config=config,
        encode_queue=encode_queue,
        error_queue=queue.Queue(),
        stop_event=threading.Event(),
    )

    item = encode_queue.get_nowait()
    assert isinstance(item, StreamEnd)
    assert item.next_source_frame == 3
    assert runtime_calls == []
