from __future__ import annotations

from typing import Any

from app.planning import ResumeState, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_raw_stage import run_raw_stage_worker
from app.processing.streaming.pipeline_raw_state import create_raw_pipeline_state


def test_run_raw_stage_worker_forwards_runtime_state(monkeypatch) -> None:
    state = create_raw_pipeline_state()
    calls: list[dict[str, Any]] = []

    def fake_runner(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("app.processing.streaming.pipeline_raw_stage.run_stage_worker_pipeline", fake_runner)

    run_raw_stage_worker(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path="input.mp4",
        decode_config={"mode": "software"},
        stage_plan=StagePlan(
            pre_steps=[],
            interpolation_step=None,
            post_steps=[],
            total_encoded_frames=1,
        ),
        tensor_backend_name="onnx",
        progress_callbacks=[],
        video_info={"source_fps": 24.0, "source_frames": 1, "width": 1, "height": 1},
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        metrics=PipelineMetrics(),
        state=state,
    )

    assert len(calls) == 1
    call = calls[0]
    assert call["encode_queue"] is state.encode_queue
    assert call["error_queue"] is state.error_queue
    assert call["stop_event"] is state.stop_event
    assert call["input_path"] == "input.mp4"
    assert call["tensor_backend_name"] == "onnx"
