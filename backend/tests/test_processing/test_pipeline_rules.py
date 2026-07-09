from __future__ import annotations

from app.planning import ProcessingStep, StagePlan, build_stage_plan
from app.processing.streaming.pipeline_rules import (
    build_config_snapshot,
    resolved_output_dimensions,
    resolved_stream_fps,
    should_use_stage_file_pipeline,
    stage_file_resume_source_frames,
)


def test_build_config_snapshot_captures_signature_relevant_inputs(tmp_path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "onnx", "onnx_model": "sr.onnx"},
        stage_name="01_super_resolution",
    )

    snapshot = build_config_snapshot(
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx264"},
        workflow_config={"fpsMode": "multi"},
        output_config={"segmentFrames": 0, "ignored": True},
        processing_steps=[step],
        video_info={
            "width": 320,
            "height": 180,
            "source_fps": 24.0,
            "source_frames": 5,
            "duration": 5 / 24,
        },
    )

    assert snapshot == {
        "input_path": str(input_path.resolve()),
        "output_path": str(output_path.resolve()),
        "decode_config": {"mode": "software"},
        "encode_config": {"codec": "libx264"},
        "workflow_config": {"fpsMode": "multi"},
        "output_config": {"segmentFrames": 1000},
        "processing_steps": [
            {
                "algorithm_type": "super_resolution",
                "algorithm_kwargs": {
                    "scale_factor": 2.0,
                    "sr_algorithm": "onnx",
                    "onnx_model": "sr.onnx",
                },
                "stage_name": "01_super_resolution",
            }
        ],
        "video_info": {
            "width": 320,
            "height": 180,
            "source_fps": 24.0,
            "source_frames": 5,
        },
    }


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
        total_output_frames=28,
        total_encoded_frames=28,
        total_pairs=9,
    )

    assert resolved_output_dimensions(
        video_info={"width": 320, "height": 180},
        stage_plan=stage_plan,
    ) == (1280, 720)
    assert resolved_stream_fps(24.0, stage_plan) == 72.0


def test_resolved_stream_fps_uses_source_fps_without_interpolation() -> None:
    stage_plan = build_stage_plan([], 5, source_duration=5 / 24, output_fps=None)

    assert resolved_stream_fps(24.0, stage_plan) == 24.0
