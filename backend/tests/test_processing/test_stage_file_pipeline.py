from __future__ import annotations

from pathlib import Path
from typing import Any

import app.processing.streaming.stage_file_pipeline as stage_file_pipeline
from app.planning import ProcessingStep, ResumeState, SegmentManifest, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics


def test_stage_file_pipeline_runs_each_stage_and_finalizes_intermediate_output(monkeypatch, tmp_path) -> None:
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
    input_path = str(tmp_path / "input.mp4")
    output_path = str(tmp_path / "final.mp4")
    stage_calls: list[dict[str, Any]] = []
    finalized_outputs: list[dict[str, Any]] = []

    def fake_run_single_stage_file_chunks(**kwargs: Any) -> int:
        stage_calls.append(
            {
                "algorithm": kwargs["step"].algorithm_type,
                "encode_config": kwargs["encode_config"],
                "encode_output_fps": kwargs["encode_output_fps"],
                "input_fps": kwargs["input_fps"],
                "input_frame_count": kwargs["input_frame_count"],
                "input_height": kwargs["input_height"],
                "input_path": kwargs["input_path"],
                "input_width": kwargs["input_width"],
                "manifest": kwargs["manifest"],
                "output_fps": kwargs["output_fps"],
                "output_frame_count": kwargs["output_frame_count"],
                "output_height": kwargs["output_height"],
                "output_width": kwargs["output_width"],
                "stage_index": kwargs["stage_index"],
                "stage_total": kwargs["stage_total"],
                "tensor_backend_name": kwargs["tensor_backend_name"],
            }
        )
        return int(kwargs["output_frame_count"])

    def fake_finalize_segmented_output(**kwargs: Any) -> str:
        finalized_outputs.append(
            {
                "completed_output_frames": kwargs["completed_output_frames"],
                "input_path": kwargs["input_path"],
                "output_path": kwargs["output_path"],
                "total_output_frames": kwargs["total_output_frames"],
            }
        )
        Path(kwargs["output_path"]).write_bytes(b"stage")
        return str(kwargs["output_path"])

    monkeypatch.setattr(stage_file_pipeline, "run_single_stage_file_chunks", fake_run_single_stage_file_chunks)
    monkeypatch.setattr(stage_file_pipeline, "finalize_segmented_output", fake_finalize_segmented_output)

    completed = stage_file_pipeline.run_stage_file_pipeline(
        ffmpeg=object(),
        input_path=input_path,
        decode_config={},
        encode_config={"container": "mp4", "keepAudio": True},
        manifest=manifest,
        stage_plan=stage_plan,
        tensor_backend_name="pytorch",
        progress_callbacks=[lambda *_args, **_kwargs: None, lambda *_args, **_kwargs: None],
        video_info={"width": 1, "height": 1, "source_fps": 24.0, "source_frames": 5},
        resume_state=ResumeState(completed_output_frames=0, start_source_frame=0, completed_segments=[]),
        segment_frames=2,
        output_path=output_path,
        output_fps=None,
        metrics=PipelineMetrics(),
        python_executable="python",
    )

    assert completed == 9
    assert [call["algorithm"] for call in stage_calls] == ["frame_interpolation", "super_resolution"]
    assert [call["stage_index"] for call in stage_calls] == [1, 2]
    assert [call["stage_total"] for call in stage_calls] == [2, 2]
    assert stage_calls[0]["input_path"] == input_path
    assert stage_calls[0]["input_frame_count"] == 5
    assert stage_calls[0]["output_frame_count"] == 9
    assert stage_calls[0]["input_fps"] == 24.0
    assert stage_calls[0]["output_fps"] == 48.0
    assert stage_calls[0]["input_width"] == 1
    assert stage_calls[0]["output_width"] == 1
    assert stage_calls[0]["encode_config"]["keepAudio"] is False
    assert stage_calls[0]["encode_output_fps"] is None

    assert len(finalized_outputs) == 1
    intermediate_output_path = str(stage_calls[0]["manifest"].output_path)
    assert stage_calls[1]["input_path"] == intermediate_output_path
    assert stage_calls[1]["input_frame_count"] == 9
    assert stage_calls[1]["output_frame_count"] == 9
    assert stage_calls[1]["input_fps"] == 48.0
    assert stage_calls[1]["output_fps"] == 48.0
    assert stage_calls[1]["input_width"] == 1
    assert stage_calls[1]["output_width"] == 4
    assert stage_calls[1]["manifest"] is manifest
    assert stage_calls[1]["encode_config"]["keepAudio"] is True
    assert stage_calls[1]["tensor_backend_name"] == "pytorch"

    assert finalized_outputs == [
        {
            "completed_output_frames": 9,
            "input_path": input_path,
            "output_path": intermediate_output_path,
            "total_output_frames": 9,
        }
    ]
