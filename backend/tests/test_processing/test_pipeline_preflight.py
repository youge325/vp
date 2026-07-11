from __future__ import annotations

from app.planning import ProcessingStep
from app.processing.streaming.pipeline_preflight import build_streaming_pipeline_preflight


class _FakeFFmpeg:
    def get_video_info(self, _input_path: str) -> dict[str, object]:
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 320,
                    "height": 180,
                }
            ]
        }

    def get_fps(self, _input_path: str) -> float:
        return 24.0

    def get_frame_count(self, _input_path: str) -> int:
        return 5

    def get_duration(self, _input_path: str) -> float:
        return 5 / 24

    def has_audio(self, _input_path: str) -> bool:
        return True


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

    preflight = build_streaming_pipeline_preflight(
        ffmpeg=_FakeFFmpeg(),
        input_path=str(input_path),
        output_path=str(output_path),
        decode_config={"mode": "software"},
        encode_config={"codec": "libx265"},
        workflow_config={"fpsMode": "target"},
        output_config={"segmentFrames": 0},
        processing_steps=steps,
        output_fps=None,
    )

    assert preflight.video_info == {
        "width": 320,
        "height": 180,
        "source_fps": 24.0,
        "source_frames": 5,
        "duration": 5 / 24,
        "has_audio": True,
    }
    assert preflight.stage_plan.total_encoded_frames == 9
    assert not hasattr(preflight.stage_plan, "total_output_frames")
    assert not hasattr(preflight.stage_plan, "total_pairs")
    assert preflight.use_stage_file_pipeline is True
    assert preflight.resume_source_frames == 9
    assert preflight.output_width == 640
    assert preflight.output_height == 360
    assert preflight.segment_frames == 1000
    assert len(preflight.signature) == 64
    assert preflight.config_snapshot["output_config"] == {"segmentFrames": 1000}
