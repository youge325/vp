from __future__ import annotations

from pathlib import Path
from typing import Any

import app.processing.streaming.stage_file_pipeline as stage_file_pipeline
from app.planning import ProcessingStep, ResumeState, SegmentManifest, build_stage_plan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig


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
    ffmpeg = object()
    decode_config: dict[str, Any] = {}
    encode_config: dict[str, Any] = {"container": "mp4", "keepAudio": True}
    metrics = PipelineMetrics()
    stage_calls: list[dict[str, Any]] = []
    finalized_outputs: list[dict[str, Any]] = []

    def fake_run_single_stage_file_chunks(**kwargs: Any) -> int:
        config = kwargs["config"]
        assert isinstance(config, StageFileRuntimeConfig)
        stage_calls.append(
            {
                "config": config,
                "input_frame_count": kwargs["input_frame_count"],
                "manifest": kwargs["manifest"],
                "output_frame_count": kwargs["output_frame_count"],
            }
        )
        return int(kwargs["output_frame_count"])

    def fake_finalize_segmented_output(**kwargs: Any) -> None:
        finalized_outputs.append(
            {
                "completed_output_frames": kwargs["completed_output_frames"],
                "input_path": kwargs["input_path"],
                "output_path": kwargs["output_path"],
                "total_output_frames": kwargs["total_output_frames"],
            }
        )
        Path(kwargs["output_path"]).write_bytes(b"stage")

    monkeypatch.setattr(stage_file_pipeline, "run_single_stage_file_chunks", fake_run_single_stage_file_chunks)
    monkeypatch.setattr(stage_file_pipeline, "finalize_segmented_output", fake_finalize_segmented_output)

    completed = stage_file_pipeline.run_stage_file_pipeline(
        ffmpeg=ffmpeg,
        input_path=input_path,
        decode_config=decode_config,
        encode_config=encode_config,
        manifest=manifest,
        stage_plan=stage_plan,
        tensor_backend_name="pytorch",
        progress_callbacks=[lambda *_args, **_kwargs: None, lambda *_args, **_kwargs: None],
        video_info={"width": 1, "height": 1, "source_fps": 24.0, "source_frames": 5},
        resume_state=ResumeState(completed_output_frames=0, start_source_frame=0, completed_segments=[]),
        segment_frames=2,
        output_path=output_path,
        output_fps=None,
        metrics=metrics,
    )

    assert completed == 9
    configs = [call["config"] for call in stage_calls]
    assert [config.step.algorithm_type for config in configs] == ["frame_interpolation", "super_resolution"]
    assert [config.stage_index for config in configs] == [1, 2]
    assert [config.stage_total for config in configs] == [2, 2]
    assert configs[0].input_path == input_path
    assert configs[0].ffmpeg is ffmpeg
    assert all(config.decode_config is decode_config for config in configs)
    assert all(config.metrics is metrics for config in configs)
    assert stage_calls[0]["input_frame_count"] == 5
    assert stage_calls[0]["output_frame_count"] == 9
    assert configs[0].output_fps == 48.0
    assert configs[0].input_width == 1
    assert configs[0].output_width == 1
    assert configs[0].encode_config["keepAudio"] is False
    assert configs[0].encode_output_fps is None

    assert len(finalized_outputs) == 1
    intermediate_output_path = str(stage_calls[0]["manifest"].output_path)
    assert configs[1].input_path == intermediate_output_path
    assert stage_calls[1]["input_frame_count"] == 9
    assert stage_calls[1]["output_frame_count"] == 9
    assert configs[1].output_fps == 48.0
    assert configs[1].input_width == 1
    assert configs[1].output_width == 4
    assert stage_calls[1]["manifest"] is manifest
    assert configs[1].encode_config is encode_config
    assert configs[1].encode_config["keepAudio"] is True
    assert configs[1].tensor_backend_name == "pytorch"

    assert finalized_outputs == [
        {
            "completed_output_frames": 9,
            "input_path": input_path,
            "output_path": intermediate_output_path,
            "total_output_frames": 9,
        }
    ]
