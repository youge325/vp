from __future__ import annotations

import pytest

from app.planning.manifest import ResumeState
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import StagePlan, build_stage_plan
from app.planning.stage_projection import StageProjection
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline import process_video_streaming
from app.processing.streaming.pipeline_context import StreamingPipelinePreflight
from tests.support.streaming_runtime import create_test_manifest, ignore_worker_log
from tests.support.video_metadata import make_video_metadata


def _stage_plan(*, requires_file_pipeline: bool) -> StagePlan:
    step = (
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="01_frame_interpolation",
        )
        if requires_file_pipeline
        else ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "placeholder"},
            stage_name="01_super_resolution",
        )
    )
    return build_stage_plan(
        StageProjection((step,)),
        make_video_metadata(4, duration=4 / 24, width=640, height=360, has_audio=False),
        output_fps=None,
    )


@pytest.mark.parametrize(("use_stage_file_pipeline", "expected"), [(True, 11), (False, 7)])
def test_pipeline_composition_dispatches_from_stage_plan_and_emits_resume_status(
    monkeypatch,
    tmp_path,
    use_stage_file_pipeline: bool,
    expected: int,
) -> None:
    events: list[tuple[int, int]] = []
    calls: list[object] = []
    resume_state = ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])
    stage_plan = _stage_plan(requires_file_pipeline=use_stage_file_pipeline)
    manifest = create_test_manifest(str(tmp_path / "out.mp4"))

    monkeypatch.setattr(
        "app.processing.streaming.pipeline.prepare_streaming_manifest",
        lambda **_kwargs: (manifest, resume_state),
    )
    monkeypatch.setattr(
        "app.processing.streaming.pipeline.finalize_streaming_output",
        lambda **kwargs: kwargs["completed_output_frames"],
    )

    def fake_pipeline(*, context):
        calls.append(context)
        return expected

    target = "run_stage_file_pipeline" if use_stage_file_pipeline else "run_raw_streaming_pipeline"
    monkeypatch.setattr(f"app.processing.streaming.pipeline.{target}", fake_pipeline)

    result = process_video_streaming(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path=str(tmp_path / "input.mp4"),
        output_path=str(tmp_path / "out.mp4"),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx264"},
        preflight=StreamingPipelinePreflight(
            stage_plan=stage_plan,
            signature="sig",
            config_snapshot={},
            segment_frames=1000,
        ),
        progress_callbacks=[],
        metrics=PipelineMetrics(),
        manifest_factory=create_test_manifest,
        resume_status_sink=lambda state, total: events.append((state.completed_output_frames, total)),
        worker_log_sink=ignore_worker_log,
    )

    assert result == expected
    assert events == [(0, stage_plan.total_encoded_frames)]
    assert len(calls) == 1
