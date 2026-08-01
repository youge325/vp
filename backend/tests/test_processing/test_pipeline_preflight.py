from __future__ import annotations

import pytest

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.pipeline_preflight import build_streaming_pipeline_preflight


def test_build_streaming_pipeline_preflight_resolves_planning_context(tmp_path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"video")
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2},
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"scale_factor": 2.0, "sr_algorithm": "onnx", "onnx_model": "sr.onnx"},
            stage_name="02_super_resolution",
        ),
    ]
    video_info = VideoMetadata(
        width=320,
        height=180,
        source_fps=24.0,
        source_frames=5,
        duration=5 / 24,
        has_audio=True,
    )
    projection = StageProjection(tuple(steps))

    preflight = build_streaming_pipeline_preflight(
        video_info=video_info,
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx265"},
        workflow_config={"fpsMode": "target"},
        output_config={"segmentFrames": 1000},
        projection=projection,
        output_fps=None,
    )

    assert preflight.stage_plan.source is video_info
    assert preflight.stage_plan.processing_steps == projection.steps
    assert preflight.stage_plan.total_encoded_frames == 9
    assert preflight.stage_plan.requires_file_pipeline is True
    assert preflight.stage_plan.resume_source_frames == 9
    assert preflight.stage_plan.output_dimensions == (640, 360)
    assert preflight.segment_frames == 1000
    assert len(preflight.signature) == 64
    assert preflight.config_snapshot["output_config"] == {"segmentFrames": 1000}


def test_preflight_materializes_the_complete_stage_projection_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls = 0
    original_stages = StageProjection.stages

    def counted_stages(self, **kwargs):
        nonlocal calls
        calls += 1
        return original_stages(self, **kwargs)

    monkeypatch.setattr(StageProjection, "stages", counted_stages)
    video_info = VideoMetadata(
        width=320,
        height=180,
        source_fps=24.0,
        source_frames=5,
        duration=5 / 24,
        has_audio=False,
    )
    projection = StageProjection(
        (
            ProcessingStep(
                algorithm_type="frame_interpolation",
                algorithm_kwargs={"multi": 2},
                stage_name="01_frame_interpolation",
            ),
        )
    )
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"video")

    preflight = build_streaming_pipeline_preflight(
        video_info=video_info,
        input_path=str(input_path),
        output_path=str(tmp_path / "output.mp4"),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx265"},
        workflow_config={"fpsMode": "source"},
        output_config={"segmentFrames": 1000},
        projection=projection,
        output_fps=None,
    )

    assert preflight.stage_plan.output_dimensions == (320, 180)
    assert preflight.stage_plan.stream_fps == 48.0
    assert preflight.stage_plan.slice_stages(3)[-1].output_frames == 5
    assert calls == 1
