from __future__ import annotations

from pathlib import Path

from app.planning.manifest import ResumeState
from app.planning.processing_steps import ProcessingStep
from app.processing.streaming import stage_file_chunk_runtime, stage_file_chunks
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from tests.support.streaming_runtime import create_test_manifest, ignore_worker_log


def test_single_stage_file_chunks_finalize_manifest_segments(monkeypatch, tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    manifest = create_test_manifest(str(tmp_path / "stage.mp4"))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    calls = []
    config = StageFileRuntimeConfig(
        ffmpeg=object(),
        input_path="input.mp4",
        decode_config={},
        encode_config={"container": "mp4"},
        step=step,
        stage_index=1,
        stage_total=1,
        tensor_backend_name="paddle",
        progress_callback=None,
        input_width=16,
        input_height=16,
        output_width=64,
        output_height=64,
        output_fps=24.0,
        encode_output_fps=None,
        metrics=PipelineMetrics(),
        worker_log_sink=ignore_worker_log,
    )

    def fake_run_stage_chunk_to_file(**kwargs):
        chunk = kwargs["chunk"]
        assert kwargs["config"] is config
        assert kwargs["stage_total_frames"] == 5
        calls.append((chunk.input_start_frame, chunk.input_frame_count, chunk.written_output_frame_count))
        Path(kwargs["output_path"]).write_bytes(b"chunk")
        return chunk.written_output_frame_count

    monkeypatch.setattr(stage_file_chunk_runtime, "run_stage_chunk_to_file", fake_run_stage_chunk_to_file)

    completed = stage_file_chunks.run_single_stage_file_chunks(
        config=config,
        manifest=manifest,
        input_frame_count=5,
        output_frame_count=5,
        resume_state=ResumeState(completed_output_frames=0, start_source_frame=0, completed_segments=[]),
        start_frame=0,
        start_chunk_index=1,
        segment_frames=2,
    )

    segments = manifest.scan_completed_chunks()
    assert completed == 5
    assert calls == [(0, 2, 2), (2, 2, 2), (4, 1, 1)]
    assert [segment.frame_count for segment in segments] == [2, 2, 1]
