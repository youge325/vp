from __future__ import annotations

from collections import deque
import io
import json
import queue
import threading
from types import SimpleNamespace

import numpy as np

from app.errors import ProcessError, TaskErrorCode
from app.planning import ProcessingStep, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame
from app.processing.streaming.stage_worker_config import StageWorkerConfig
from app.processing.streaming.worker_plans import StageWorkerPlan
from app.processing.streaming.worker_processes import (
    drain_final_worker_output,
    parse_stage_event_line,
    read_worker_stderr,
)


def test_parse_stage_event_line_returns_json_event_only_for_prefixed_lines() -> None:
    assert parse_stage_event_line('VP_STAGE_EVENT {"type":"progress","current":2}') == {
        "type": "progress",
        "current": 2,
    }
    assert parse_stage_event_line("ordinary stderr") is None


def test_read_worker_stderr_forwards_tensorrt_lifecycle_logs_to_parent_stderr(capsys) -> None:
    trt_line = (
        "22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: "
        "[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x128x128"
    )
    stderr = io.BytesIO(
        (
            f"{trt_line}\n"
            "ordinary worker stderr\n"
            'VP_STAGE_EVENT {"type":"progress","stageIndex":1,"current":1,"total":5}\n'
        ).encode("utf-8")
    )
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    progress_calls: list[tuple[int, int]] = []

    read_worker_stderr(
        handle,
        [lambda current, total, **_kwargs: progress_calls.append((current, total))],
        queue.Queue(),
        threading.Event(),
    )

    captured = capsys.readouterr()
    assert trt_line in captured.err
    assert "ordinary worker stderr" not in captured.err
    assert progress_calls == [(1, 5)]
    assert list(handle.stderr_tail) == [
        trt_line,
        "ordinary worker stderr",
    ]


def test_read_worker_stderr_normalizes_legacy_error_code_string() -> None:
    event = {
        "type": "error",
        "code": "TaskErrorCode.MISSING_MODEL",
        "message": "missing aux weight",
        "details": {"path": "spynet.pdparams"},
    }
    stderr = io.BytesIO(f"VP_STAGE_EVENT {json.dumps(event)}\n".encode("utf-8"))
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    error_queue: queue.Queue[BaseException] = queue.Queue()
    stop_event = threading.Event()

    read_worker_stderr(handle, [], error_queue, stop_event)

    error = error_queue.get_nowait()
    assert isinstance(error, ProcessError)
    assert error.code == TaskErrorCode.MISSING_MODEL.value
    assert error.message == "missing aux weight"
    assert stop_event.is_set()


def test_read_worker_stderr_forwards_second_stage_zero_progress() -> None:
    events = [
        {
            "type": "progress",
            "stageIndex": 1,
            "current": 100,
            "total": 100,
        },
        {
            "type": "progress",
            "stageIndex": 2,
            "current": 0,
            "total": 200,
            "force": True,
            "heartbeat": True,
        },
    ]
    stderr = io.BytesIO("".join(f"VP_STAGE_EVENT {json.dumps(event)}\n" for event in events).encode("utf-8"))
    handle = SimpleNamespace(
        process=SimpleNamespace(stderr=stderr),
        plan=SimpleNamespace(config=SimpleNamespace(stage_index=1)),
        stderr_tail=deque(maxlen=20),
    )
    progress_calls: list[tuple[int, int, int, bool, bool]] = []
    callbacks = [
        lambda current, total, **kwargs: progress_calls.append(
            (1, current, total, bool(kwargs.get("force")), bool(kwargs.get("heartbeat")))
        ),
        lambda current, total, **kwargs: progress_calls.append(
            (2, current, total, bool(kwargs.get("force")), bool(kwargs.get("heartbeat")))
        ),
    ]

    read_worker_stderr(handle, callbacks, queue.Queue(), threading.Event())

    assert progress_calls == [(1, 100, 100, False, False), (2, 0, 200, True, True)]


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

    drain_final_worker_output(
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
