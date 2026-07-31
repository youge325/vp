from __future__ import annotations

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import StagePlan, build_stage_plan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.pipeline_rules import (
    resolved_output_dimensions,
    resolved_stream_fps,
    should_use_stage_file_pipeline,
    stage_file_resume_source_frames,
)


def test_pipeline_strategy_and_resume_domain_use_stage_rules() -> None:
    stage_plan = build_stage_plan(
        StageProjection(
            (
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
            )
        ),
        5,
        source_duration=5 / 24,
        output_fps=None,
    )

    assert should_use_stage_file_pipeline(stage_plan) is True
    assert stage_file_resume_source_frames(stage_plan, 5) == 9


def test_pipeline_strategy_stays_rawvideo_for_non_file_backed_stages() -> None:
    stage_plan = build_stage_plan(
        StageProjection(
            (
                ProcessingStep(
                    algorithm_type="super_resolution",
                    algorithm_kwargs={"scale_factor": 1.0, "sr_algorithm": "placeholder"},
                    stage_name="01_super_resolution",
                ),
            )
        ),
        5,
        source_duration=5 / 24,
        output_fps=None,
    )

    assert should_use_stage_file_pipeline(stage_plan) is False
    assert stage_file_resume_source_frames(stage_plan, 5) == 5


def test_resolved_output_dimensions_and_stream_fps_follow_stage_plan() -> None:
    stage_plan = StagePlan(
        projection=StageProjection(
            (
                ProcessingStep(
                    algorithm_type="super_resolution",
                    algorithm_kwargs={
                        "sr_algorithm": "ppmsvsr",
                        "scale_factor": 4,
                        "tensor_backend": "paddle",
                    },
                    stage_name="01_super_resolution",
                ),
                ProcessingStep(
                    algorithm_type="frame_interpolation",
                    algorithm_kwargs={"multi": 3},
                    stage_name="02_frame_interpolation",
                ),
            ),
        ),
        source_frames=10,
        source_duration=10 / 24,
        output_fps=None,
    )

    assert resolved_output_dimensions(
        video_info=VideoMetadata(
            width=320,
            height=180,
            source_fps=24.0,
            source_frames=5,
            duration=5 / 24,
            has_audio=False,
        ),
        stage_plan=stage_plan,
    ) == (1280, 720)
    assert resolved_stream_fps(24.0, stage_plan) == 72.0


def test_resolved_stream_fps_uses_source_fps_without_interpolation() -> None:
    stage_plan = build_stage_plan(StageProjection(()), 5, source_duration=5 / 24, output_fps=None)

    assert resolved_stream_fps(24.0, stage_plan) == 24.0


def test_stage_plan_projects_interpolation_fps() -> None:
    interpolation_step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 4},
        stage_name="01_frame_interpolation",
    )
    stage_plan = StagePlan(
        projection=StageProjection((interpolation_step,)),
        source_frames=1,
        source_duration=1 / 24,
        output_fps=None,
    )

    assert resolved_stream_fps(24.0, stage_plan) == 96.0
