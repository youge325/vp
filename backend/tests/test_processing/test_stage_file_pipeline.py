from __future__ import annotations

from pathlib import Path
from typing import Any

import app.processing.streaming.stage_file_pipeline as stage_file_pipeline
from app.planning.manifest import ResumeState
from app.planning.processing_steps import ProcessingStep
from app.planning.stage_plan import build_stage_plan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_context import (
    StreamingPipelineContext,
    StreamingPipelinePreflight,
)
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from tests.support.streaming_runtime import create_test_manifest, ignore_resume_status, ignore_worker_log


def test_stage_file_pipeline_runs_each_stage_and_finalizes_intermediate_output(monkeypatch, tmp_path) -> None:
    steps = [
        ProcessingStep(
            algorithm_type="frame_interpolation",
            algorithm_kwargs={"multi": 2, "tensor_backend": "pytorch"},
            stage_name="01_frame_interpolation",
        ),
        ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={
                "scale_factor": 4.0,
                "sr_algorithm": "ppmsvsr",
                "tensor_backend": "paddle",
            },
            stage_name="02_super_resolution",
        ),
    ]
    stage_plan = build_stage_plan(StageProjection(tuple(steps)), 5, source_duration=5 / 24, output_fps=None)
    manifest = create_test_manifest(str(tmp_path / "final.mp4"))
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

    context = StreamingPipelineContext(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        decode_config=decode_config,
        encode_config=encode_config,
        preflight=StreamingPipelinePreflight(
            video_info=VideoMetadata(
                width=1,
                height=1,
                source_fps=24.0,
                source_frames=5,
                duration=5 / 24,
                has_audio=False,
            ),
            stage_plan=stage_plan,
            signature="sig",
            config_snapshot={"test": True},
            output_width=4,
            output_height=4,
            segment_frames=2,
        ),
        manifest=manifest,
        resume_state=ResumeState(completed_output_frames=0, start_source_frame=0, completed_segments=[]),
        progress_callbacks=[lambda *_args, **_kwargs: None, lambda *_args, **_kwargs: None],
        output_fps=None,
        encode_progress_callback=None,
        metrics=metrics,
        manifest_factory=create_test_manifest,
        resume_status_sink=ignore_resume_status,
        worker_log_sink=ignore_worker_log,
    )
    completed = stage_file_pipeline.run_stage_file_pipeline(context=context)

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
    intermediate_output_path = str(stage_calls[0]["manifest"].workspace.output_path)
    assert configs[1].input_path == intermediate_output_path
    assert stage_calls[1]["input_frame_count"] == 9
    assert stage_calls[1]["output_frame_count"] == 9
    assert configs[1].output_fps == 48.0
    assert configs[1].input_width == 1
    assert configs[1].output_width == 4
    assert stage_calls[1]["manifest"] is manifest
    assert configs[1].encode_config is encode_config
    assert configs[1].encode_config["keepAudio"] is True
    assert configs[1].tensor_backend_name == "paddle"

    assert finalized_outputs == [
        {
            "completed_output_frames": 9,
            "input_path": input_path,
            "output_path": intermediate_output_path,
            "total_output_frames": 9,
        }
    ]
