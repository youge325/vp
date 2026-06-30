from __future__ import annotations

import io
import queue
import threading

import numpy as np

from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame
from app.processing.streaming.stage_worker import StageWorkerConfig
from app.processing.streaming.worker_pipeline import (
    StageWorkerPlan,
    _drain_final_worker_output,
    boundary_schedule_for_stage_plan,
    build_stage_worker_plans,
    parse_stage_event_line,
)


def test_worker_plan_tracks_dimensions_for_super_resolution_then_interpolation() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder", "onnx_model": "sr.onnx"},
            stage_name="01_super_resolution",
        ),
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="02_frame_interpolation",
        ),
    ]
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        source_width=2,
        source_height=3,
        source_frame_count=3,
    )

    assert [plan.output_frame_count for plan in plans] == [3, 5]
    assert plans[0].config.input_width == 2
    assert plans[0].config.input_height == 3
    assert plans[0].config.output_width == 4
    assert plans[0].config.output_height == 6
    assert plans[1].config.input_width == 4
    assert plans[1].config.input_height == 6
    assert plans[1].config.output_width == 4
    assert plans[1].config.output_height == 6
    assert plans[1].config.input_frame_count == 3


def test_worker_plan_tracks_frame_counts_for_interpolation_then_super_resolution() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder", "onnx_model": "sr.onnx"},
            stage_name="02_super_resolution",
        ),
    ]
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)

    plans = build_stage_worker_plans(
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        source_width=2,
        source_height=3,
        source_frame_count=3,
    )

    assert [plan.config.input_frame_count for plan in plans] == [3, 7]
    assert [plan.output_frame_count for plan in plans] == [7, 7]
    assert plans[0].config.output_width == 2
    assert plans[0].config.output_height == 3
    assert plans[1].config.input_width == 2
    assert plans[1].config.input_height == 3
    assert plans[1].config.output_width == 4
    assert plans[1].config.output_height == 6


def test_parse_stage_event_line_returns_json_event_only_for_prefixed_lines() -> None:
    assert parse_stage_event_line('VP_STAGE_EVENT {"type":"progress","current":2}') == {
        "type": "progress",
        "current": 2,
    }
    assert parse_stage_event_line("ordinary stderr") is None


def test_boundary_schedule_matches_interpolation_output_groups() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="01_frame_interpolation",
        )
    ]
    stage_plan = build_stage_plan(steps, 4, source_duration=1.0, output_fps=None)

    schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=1,
        source_frames=4,
    )

    assert schedule == {2: 2, 4: 3}


def test_boundary_schedule_matches_single_frame_output_groups() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0},
            stage_name="01_super_resolution",
        )
    ]
    stage_plan = build_stage_plan(steps, 4, source_duration=1.0, output_fps=None)

    schedule = boundary_schedule_for_stage_plan(
        stage_plan=stage_plan,
        start_source_frame=1,
        source_frames=4,
    )

    assert schedule == {1: 2, 2: 3}


def test_drain_final_worker_output_stops_after_expected_frame_count() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0},
        stage_name="01_super_resolution",
    )
    stage_plan = build_stage_plan([step], 1, source_duration=1.0, output_fps=None)
    final_plan = StageWorkerPlan(
        config=StageWorkerConfig(
            stage=step,
            stage_index=1,
            stage_total=1,
            stage_name="01_super_resolution",
            input_width=1,
            input_height=1,
            output_width=1,
            output_height=1,
            input_frame_count=1,
            tensor_backend_name="onnx",
        ),
        output_frame_count=1,
    )
    final_stdout = io.BytesIO(np.array([[[1, 2, 3]]], dtype=np.uint8).tobytes() + b"tail")
    encode_queue: queue.Queue = queue.Queue()
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    _drain_final_worker_output(
        final_stdout=final_stdout,
        final_plan=final_plan,
        stage_plan=stage_plan,
        resume_state=type("ResumeState", (), {"completed_output_frames": 0, "start_source_frame": 0})(),
        source_frames=1,
        encode_queue=encode_queue,
        error_queue=error_queue,
        stop_event=stop_event,
        metrics=PipelineMetrics(),
    )

    assert error_queue.empty()
    item = encode_queue.get_nowait()
    assert isinstance(item, EncodedFrame)
    assert int(item.frame[0, 0, 0]) == 1
