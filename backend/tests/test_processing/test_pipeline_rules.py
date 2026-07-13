from __future__ import annotations

from app.processing.streaming import pipeline_rules as pipeline_rules_module
from app.planning import ProcessingStep, StagePlan, build_stage_plan
from app.processing.streaming.pipeline_rules import (
    resolved_output_dimensions,
    resolved_stream_fps,
    should_use_stage_file_pipeline,
    stage_file_resume_source_frames,
)


def test_pipeline_strategy_and_resume_domain_use_stage_rules() -> None:
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

    assert should_use_stage_file_pipeline(stage_plan) is True
    assert stage_file_resume_source_frames(stage_plan, 5) == 9


def test_pipeline_strategy_stays_rawvideo_for_non_file_backed_stages() -> None:
    stage_plan = build_stage_plan(
        [
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={"scale_factor": 1.0, "sr_algorithm": "placeholder"},
                stage_name="01_super_resolution",
            )
        ],
        5,
        source_duration=5 / 24,
        output_fps=None,
    )

    assert should_use_stage_file_pipeline(stage_plan) is False
    assert stage_file_resume_source_frames(stage_plan, 5) == 5


def test_resolved_output_dimensions_and_stream_fps_follow_stage_plan() -> None:
    stage_plan = StagePlan(
        pre_steps=[
            ProcessingStep(
                algorithm_type="super_resolution",
                algorithm_kwargs={
                    "sr_algorithm": "ppmsvsr",
                    "scale_factor": 4,
                    "tensor_backend": "paddle",
                },
                stage_name="01_super_resolution",
            )
        ],
        interpolation_step=ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 3},
            stage_name="02_frame_interpolation",
        ),
        post_steps=[],
        total_encoded_frames=28,
    )

    assert resolved_output_dimensions(
        video_info={"width": 320, "height": 180},
        stage_plan=stage_plan,
    ) == (1280, 720)
    assert resolved_stream_fps(24.0, stage_plan) == 72.0


def test_resolved_stream_fps_uses_source_fps_without_interpolation() -> None:
    stage_plan = build_stage_plan([], 5, source_duration=5 / 24, output_fps=None)

    assert resolved_stream_fps(24.0, stage_plan) == 24.0


def test_resolved_stream_fps_delegates_interpolation_math_to_stage_rule(monkeypatch) -> None:
    interpolation_step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 4},
        stage_name="01_frame_interpolation",
    )
    stage_plan = StagePlan(
        pre_steps=[],
        interpolation_step=interpolation_step,
        post_steps=[],
        total_encoded_frames=1,
    )
    calls: list[tuple[ProcessingStep, float]] = []
    monkeypatch.setattr(
        pipeline_rules_module,
        "stage_output_fps",
        lambda step, source_fps: calls.append((step, source_fps)) or 96.0,
    )

    assert resolved_stream_fps(24.0, stage_plan) == 96.0
    assert calls == [(interpolation_step, 24.0)]
