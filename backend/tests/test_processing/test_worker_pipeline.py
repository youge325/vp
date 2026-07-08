from __future__ import annotations

import io
import json
from pathlib import Path
import queue
import threading
from collections import deque
from types import SimpleNamespace

import numpy as np

import app.processing.streaming.pipeline as streaming_pipeline
import app.processing.streaming.worker_pipeline as worker_pipeline
from app.errors import ProcessError, TaskErrorCode
from app.planning import ProcessingStep, SegmentManifest, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.queues import EncodedFrame
from app.processing.streaming.stage_rules import (
    ordered_steps,
    stage_output_dimensions,
    stage_output_frame_count,
    stage_tensor_backend_name,
)
from app.processing.streaming.stage_worker import StageWorkerConfig
from app.processing.streaming.worker_pipeline import (
    _drain_final_worker_output,
    _read_worker_stderr,
    parse_stage_event_line,
    run_stage_file_pipeline,
)
from app.processing.streaming.worker_plans import (
    StageWorkerPlan,
    boundary_schedule_for_stage_plan,
    build_stage_chunk_plans,
    build_stage_worker_plans,
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


def test_stage_rules_centralize_stage_order_dimensions_and_backend_selection() -> None:
    steps = [
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 4.0,
                "sr_algorithm": "ppmsvsr",
                "tensor_backend": "paddle",
            },
            stage_name="01_super_resolution",
        ),
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="02_frame_interpolation",
        ),
    ]
    stage_plan = build_stage_plan(steps, 3, source_duration=1.0, output_fps=None)

    assert [step.stage_name for step in ordered_steps(stage_plan)] == [
        "01_super_resolution",
        "02_frame_interpolation",
    ]
    assert stage_tensor_backend_name(steps[0], "onnx") == "paddle"
    assert stage_output_dimensions(steps[0], input_width=2, input_height=3) == (8, 12)
    assert stage_output_frame_count(steps[1], 3) == 7


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
    assert [plan.config.output_frame_count for plan in plans] == [7, 7]
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

    _read_worker_stderr(
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


def test_interpolation_stage_chunks_use_lookahead_and_skip_duplicate_boundary() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2},
        stage_name="01_frame_interpolation",
    )

    chunks = build_stage_chunk_plans(step, input_frame_count=5, segment_frames=2)

    assert [
        (
            chunk.input_start_frame,
            chunk.input_frame_count,
            chunk.logical_input_frame_count,
            chunk.raw_output_frame_count,
            chunk.skip_output_frames,
            chunk.written_output_frame_count,
        )
        for chunk in chunks
    ] == [
        (0, 3, 2, 5, 0, 5),
        (2, 3, 2, 5, 1, 4),
        (4, 1, 1, 1, 1, 0),
    ]
    assert sum(chunk.written_output_frame_count for chunk in chunks) == 9


def test_super_resolution_stage_chunks_keep_input_frame_counts_bounded() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="02_super_resolution",
    )

    chunks = build_stage_chunk_plans(step, input_frame_count=5, segment_frames=2)

    assert [
        (chunk.input_start_frame, chunk.input_frame_count, chunk.written_output_frame_count) for chunk in chunks
    ] == [
        (0, 2, 2),
        (2, 2, 2),
        (4, 1, 1),
    ]
    assert max(chunk.input_frame_count for chunk in chunks) == 2
    assert sum(chunk.written_output_frame_count for chunk in chunks) == 5


def test_single_stage_file_chunks_finalize_manifest_segments(monkeypatch, tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    manifest = SegmentManifest(str(tmp_path / "stage.mp4"))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    calls = []

    def fake_run_stage_chunk_to_file(**kwargs):
        chunk = kwargs["chunk"]
        calls.append((chunk.input_start_frame, chunk.input_frame_count, chunk.written_output_frame_count))
        Path(kwargs["output_path"]).write_bytes(b"chunk")
        return chunk.written_output_frame_count

    monkeypatch.setattr(worker_pipeline, "_run_stage_chunk_to_file", fake_run_stage_chunk_to_file)

    completed = worker_pipeline._run_single_stage_file_chunks(
        ffmpeg=object(),
        input_path="input.mp4",
        decode_config={},
        encode_config={"container": "mp4"},
        manifest=manifest,
        step=step,
        stage_index=1,
        stage_total=1,
        tensor_backend_name="paddle",
        progress_callback=None,
        input_width=16,
        input_height=16,
        output_width=64,
        output_height=64,
        input_frame_count=5,
        output_frame_count=5,
        input_fps=24.0,
        output_fps=24.0,
        encode_output_fps=None,
        resume_state=type("ResumeState", (), {"completed_output_frames": 0, "completed_segments": []})(),
        start_frame=0,
        start_chunk_index=1,
        segment_frames=2,
        metrics=PipelineMetrics(),
        python_executable="python",
    )

    segments = manifest.read_completed_segments()
    assert completed == 5
    assert calls == [(0, 2, 2), (2, 2, 2), (4, 1, 1)]
    assert [segment.frame_count for segment in segments] == [2, 2, 1]


def test_stage_file_pipeline_runs_each_stage_as_bounded_segments(monkeypatch, tmp_path) -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
            stage_name="02_super_resolution",
        ),
    ]
    stage_plan = build_stage_plan(steps, 5, source_duration=5 / 24, output_fps=None)
    manifest = SegmentManifest(str(tmp_path / "final.mp4"))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    calls = []

    class FakeFFmpeg:
        def concat_videos(self, segment_paths, output_path):
            Path(output_path).write_bytes(b"concat")
            return output_path

        def has_audio(self, _input_path):
            return False

    def fake_run_stage_chunk_to_file(**kwargs):
        chunk = kwargs["chunk"]
        calls.append(
            (
                kwargs["step"].algorithm_type,
                chunk.input_start_frame,
                chunk.input_frame_count,
                chunk.written_output_frame_count,
            )
        )
        Path(kwargs["output_path"]).write_bytes(b"chunk")
        return chunk.written_output_frame_count

    monkeypatch.setattr(worker_pipeline, "_run_stage_chunk_to_file", fake_run_stage_chunk_to_file)

    completed = run_stage_file_pipeline(
        ffmpeg=FakeFFmpeg(),
        input_path=str(tmp_path / "input.mp4"),
        decode_config={},
        encode_config={"container": "mp4", "keepAudio": False},
        manifest=manifest,
        stage_plan=stage_plan,
        tensor_backend_name="pytorch",
        progress_callbacks=[lambda *_args, **_kwargs: None, lambda *_args, **_kwargs: None],
        video_info={"width": 1, "height": 1, "source_fps": 24.0, "source_frames": 5},
        resume_state=type(
            "ResumeState", (), {"completed_output_frames": 0, "start_source_frame": 0, "completed_segments": []}
        )(),
        segment_frames=2,
        output_path=str(tmp_path / "final.mp4"),
        output_fps=None,
        metrics=PipelineMetrics(),
        python_executable="python",
    )

    assert completed == 9
    assert [call for call in calls if call[0] == "frame_interpolation"] == [
        ("frame_interpolation", 0, 3, 5),
        ("frame_interpolation", 2, 3, 4),
    ]
    assert max(call[2] for call in calls if call[0] == "super_resolution") == 2
    assert sum(segment.frame_count for segment in manifest.read_completed_segments()) == 9


def test_stage_file_resume_source_frames_use_final_stage_input_domain() -> None:
    stage_plan = build_stage_plan(
        [
            ProcessingStep(
                algorithm_type="frame_interpolation",
                algorithm_kwargs={"multi": 2},
                stage_name="01_frame_interpolation",
            ),
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
                stage_name="02_super_resolution",
            ),
        ],
        5,
        source_duration=5 / 24,
        output_fps=None,
    )

    assert streaming_pipeline._stage_file_resume_source_frames(stage_plan, 5) == 9


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

    _read_worker_stderr(handle, [], error_queue, stop_event)

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

    _read_worker_stderr(handle, callbacks, queue.Queue(), threading.Event())

    assert progress_calls == [(1, 100, 100, False, False), (2, 0, 200, True, True)]


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
