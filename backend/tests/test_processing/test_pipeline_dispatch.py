from __future__ import annotations

from app.planning.manifest import ResumeState
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import StagePlan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.pipeline_context import (
    StreamingPipelineContext,
    StreamingPipelinePreflight,
)
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_dispatch import run_streaming_pipeline
from app.processing.streaming.runtime_ports import ResumeStatusSink
from tests.support.streaming_runtime import create_test_manifest, ignore_resume_status, ignore_worker_log


def _stage_plan() -> StagePlan:
    return StagePlan(
        projection=StageProjection(
            (
                ProcessingStep(
                    algorithm_type="super_resolution",
                    algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder"},
                    stage_name="01_super_resolution",
                ),
            )
        ),
        source_frames=4,
        source_duration=4 / 24,
        output_fps=None,
    )


def _resume_state() -> ResumeState:
    return ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])


def _context(
    tmp_path,
    *,
    use_stage_file_pipeline: bool,
    resume_status_sink: ResumeStatusSink = ignore_resume_status,
) -> StreamingPipelineContext:
    stage_plan = _stage_plan()
    return StreamingPipelineContext(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path=str(tmp_path / "input.mp4"),
        output_path=str(tmp_path / "out.mp4"),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx264"},
        preflight=StreamingPipelinePreflight(
            video_info=VideoMetadata(
                width=640,
                height=360,
                source_fps=24.0,
                source_frames=4,
                duration=4 / 24,
                has_audio=False,
            ),
            stage_plan=stage_plan,
            signature="sig",
            config_snapshot={},
            use_stage_file_pipeline=use_stage_file_pipeline,
            resume_source_frames=4,
            output_width=640,
            output_height=360,
            segment_frames=1000,
        ),
        manifest=create_test_manifest(str(tmp_path / "out.mp4")),
        resume_state=_resume_state(),
        progress_callbacks=[],
        output_fps=None,
        encode_progress_callback=None,
        metrics=PipelineMetrics(),
        manifest_factory=create_test_manifest,
        resume_status_sink=resume_status_sink,
        worker_log_sink=ignore_worker_log,
    )


def test_run_streaming_pipeline_dispatches_stage_file_pipeline_and_emits_resume_status(monkeypatch, tmp_path) -> None:
    events: list[tuple[int, int]] = []
    calls: dict[str, object] = {}

    def fake_stage_file_pipeline(**kwargs):
        calls.update(kwargs)
        return 11

    monkeypatch.setattr("app.processing.streaming.pipeline_dispatch.run_stage_file_pipeline", fake_stage_file_pipeline)

    context = _context(
        tmp_path,
        use_stage_file_pipeline=True,
        resume_status_sink=lambda state, total: events.append((state.completed_output_frames, total)),
    )
    result = run_streaming_pipeline(context=context)

    assert result == 11
    assert events == [(0, 4)]
    assert calls == {"context": context}


def test_run_streaming_pipeline_dispatches_raw_pipeline_without_worker_chain_coupling(monkeypatch, tmp_path) -> None:
    events: list[tuple[int, int]] = []
    calls: dict[str, object] = {}

    def fake_raw_pipeline(**kwargs):
        calls.update(kwargs)
        return 7

    monkeypatch.setattr("app.processing.streaming.pipeline_dispatch.run_raw_streaming_pipeline", fake_raw_pipeline)

    context = _context(
        tmp_path,
        use_stage_file_pipeline=False,
        resume_status_sink=lambda state, total: events.append((state.completed_output_frames, total)),
    )
    result = run_streaming_pipeline(context=context)

    assert result == 7
    assert events == [(0, 4)]
    assert calls == {"context": context}
