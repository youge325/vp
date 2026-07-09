from __future__ import annotations

from app.planning import ProcessingStep, ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_dispatch import run_streaming_pipeline


def _stage_plan() -> StagePlan:
    return StagePlan(
        pre_steps=[
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder"},
                stage_name="01_super_resolution",
            )
        ],
        interpolation_step=None,
        post_steps=[],
        total_output_frames=4,
        total_encoded_frames=4,
        total_pairs=3,
    )


def _resume_state() -> ResumeState:
    return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])


def test_run_streaming_pipeline_dispatches_stage_file_pipeline_and_emits_resume_status(monkeypatch, tmp_path) -> None:
    events: list[tuple[int, int]] = []
    calls: dict[str, object] = {}

    def fake_stage_file_pipeline(**kwargs):
        calls.update(kwargs)
        return 11

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_dispatch.emit_resume_status_event",
        lambda *, resume_state, total_output_frames: events.append(
            (resume_state.completed_output_frames, total_output_frames)
        ),
    )
    monkeypatch.setattr("app.processing.streaming.pipeline_dispatch.run_stage_file_pipeline", fake_stage_file_pipeline)

    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    stage_plan = _stage_plan()
    result = run_streaming_pipeline(
        ffmpeg=object(),
        input_path=str(tmp_path / "input.mp4"),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx264"},
        manifest=manifest,
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        progress_callbacks=[],
        video_info={"source_fps": 24.0, "source_frames": 4},
        output_width=640,
        output_height=360,
        resume_state=_resume_state(),
        segment_frames=1000,
        use_stage_file_pipeline=True,
        output_path=str(tmp_path / "out.mp4"),
        output_fps=None,
        encode_progress_callback=None,
        metrics=PipelineMetrics(),
    )

    assert result == 11
    assert events == [(0, 4)]
    assert calls["manifest"] is manifest
    assert calls["stage_plan"] is stage_plan
    assert calls["segment_frames"] == 1000
    assert "signature" not in calls
    assert "output_width" not in calls


def test_run_streaming_pipeline_dispatches_raw_pipeline_without_worker_chain_coupling(monkeypatch, tmp_path) -> None:
    events: list[tuple[int, int]] = []
    calls: dict[str, object] = {}

    def fake_raw_pipeline(**kwargs):
        calls.update(kwargs)
        return 7

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_dispatch.emit_resume_status_event",
        lambda *, resume_state, total_output_frames: events.append(
            (resume_state.completed_output_frames, total_output_frames)
        ),
    )
    monkeypatch.setattr("app.processing.streaming.pipeline_dispatch.run_raw_streaming_pipeline", fake_raw_pipeline)

    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    stage_plan = _stage_plan()
    result = run_streaming_pipeline(
        ffmpeg=object(),
        input_path=str(tmp_path / "input.mp4"),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx264"},
        manifest=manifest,
        stage_plan=stage_plan,
        tensor_backend_name="onnx",
        progress_callbacks=[],
        video_info={"source_fps": 24.0, "source_frames": 4},
        output_width=640,
        output_height=360,
        resume_state=_resume_state(),
        segment_frames=1000,
        use_stage_file_pipeline=False,
        output_path=str(tmp_path / "out.mp4"),
        output_fps=None,
        encode_progress_callback=None,
        metrics=PipelineMetrics(),
    )

    assert result == 7
    assert events == [(0, 4)]
    assert "signature" not in calls
    assert calls["output_width"] == 640
    assert calls["output_height"] == 360
    assert "stage_worker_runner" not in calls
