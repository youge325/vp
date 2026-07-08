from __future__ import annotations

from pathlib import Path

import app.processing.streaming.stage_file_chunks as stage_file_chunks
from app.planning import ProcessingStep, SegmentManifest, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_pipeline import run_stage_file_pipeline


def test_stage_file_pipeline_runs_each_stage_as_bounded_segments(monkeypatch, tmp_path) -> None:
    steps = [
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
    ]
    stage_plan = build_stage_plan(steps, 5, source_duration=5 / 24, output_fps=None)
    manifest = SegmentManifest(str(tmp_path / "final.mp4"))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    calls = []

    class FakeFFmpeg:
        def concat_videos(self, segment_paths, output_path):
            Path(output_path).write_bytes(b"concat")
            return output_path

        def has_audio(self, _input_path):
            return False

    def fake_run_stage_chunk_to_file(**kwargs):
        chunk = kwargs["chunk"]
        calls.append(
            (
                kwargs["step"].algorithm_type,
                chunk.input_start_frame,
                chunk.input_frame_count,
                chunk.written_output_frame_count,
            )
        )
        Path(kwargs["output_path"]).write_bytes(b"chunk")
        return chunk.written_output_frame_count

    monkeypatch.setattr(stage_file_chunks, "_run_stage_chunk_to_file", fake_run_stage_chunk_to_file)

    completed = run_stage_file_pipeline(
        ffmpeg=FakeFFmpeg(),
        input_path=str(tmp_path / "input.mp4"),
        decode_config={},
        encode_config={"container": "mp4", "keepAudio": False},
        manifest=manifest,
        stage_plan=stage_plan,
        tensor_backend_name="pytorch",
        progress_callbacks=[lambda *_args, **_kwargs: None, lambda *_args, **_kwargs: None],
        video_info={"width": 1, "height": 1, "source_fps": 24.0, "source_frames": 5},
        resume_state=type(
            "ResumeState", (), {"completed_output_frames": 0, "start_source_frame": 0, "completed_segments": []}
        )(),
        segment_frames=2,
        output_path=str(tmp_path / "final.mp4"),
        output_fps=None,
        metrics=PipelineMetrics(),
        python_executable="python",
    )

    assert completed == 9
    assert [call for call in calls if call[0] == "frame_interpolation"] == [
        ("frame_interpolation", 0, 3, 5),
        ("frame_interpolation", 2, 3, 4),
    ]
    assert max(call[2] for call in calls if call[0] == "super_resolution") == 2
    assert sum(segment.frame_count for segment in manifest.read_completed_segments()) == 9
