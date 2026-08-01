from __future__ import annotations

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from tests.support.video_metadata import make_video_metadata


def test_stage_plan_owns_file_pipeline_and_resume_domain_facts() -> None:
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
        make_video_metadata(5, duration=5 / 24),
        output_fps=None,
    )

    assert stage_plan.requires_file_pipeline is True
    assert stage_plan.resume_source_frames == 9


def test_stage_plan_stays_rawvideo_for_non_file_backed_stages() -> None:
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
        make_video_metadata(5, duration=5 / 24),
        output_fps=None,
    )

    assert stage_plan.requires_file_pipeline is False
    assert stage_plan.resume_source_frames == 5


def test_stage_plan_delegates_geometry_and_fps_to_projection() -> None:
    stage_plan = build_stage_plan(
        StageProjection(
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
        make_video_metadata(10, duration=10 / 24),
        output_fps=None,
    )

    assert stage_plan.output_dimensions == (1280, 720)
    assert stage_plan.stream_fps == 72.0


def test_projection_preserves_fps_without_interpolation() -> None:
    stage_plan = build_stage_plan(
        StageProjection(()),
        make_video_metadata(5, duration=5 / 24),
        output_fps=None,
    )

    assert stage_plan.stream_fps == 24.0
