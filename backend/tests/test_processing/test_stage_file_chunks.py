from __future__ import annotations

from pathlib import Path

from app.planning import ProcessingStep, SegmentManifest
from app.processing.streaming import stage_file_chunk_runtime, stage_file_chunks, stage_file_rules
from app.processing.streaming.metrics import PipelineMetrics


def test_single_stage_file_chunks_finalize_manifest_segments(monkeypatch, tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    manifest = SegmentManifest(str(tmp_path / "stage.mp4"))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    calls = []

    def fake_run_stage_chunk_to_file(**kwargs):
        chunk = kwargs["chunk"]
        calls.append((chunk.input_start_frame, chunk.input_frame_count, chunk.written_output_frame_count))
        Path(kwargs["output_path"]).write_bytes(b"chunk")
        return chunk.written_output_frame_count

    monkeypatch.setattr(stage_file_chunk_runtime, "run_stage_chunk_to_file", fake_run_stage_chunk_to_file)

    completed = stage_file_chunks.run_single_stage_file_chunks(
        ffmpeg=object(),
        input_path="input.mp4",
        decode_config={},
        encode_config={"container": "mp4"},
        manifest=manifest,
        step=step,
        stage_index=1,
        stage_total=1,
        tensor_backend_name="paddle",
        progress_callback=None,
        input_width=16,
        input_height=16,
        output_width=64,
        output_height=64,
        input_frame_count=5,
        output_frame_count=5,
        input_fps=24.0,
        output_fps=24.0,
        encode_output_fps=None,
        resume_state=type("ResumeState", (), {"completed_output_frames": 0, "completed_segments": []})(),
        start_frame=0,
        start_chunk_index=1,
        segment_frames=2,
        metrics=PipelineMetrics(),
        python_executable="python",
    )

    segments = manifest.scan_completed_chunks()
    assert completed == 5
    assert calls == [(0, 2, 2), (2, 2, 2), (4, 1, 1)]
    assert [segment.frame_count for segment in segments] == [2, 2, 1]


def test_stage_file_rules_build_safe_signature_and_empty_resume(tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01 super/resolution",
    )

    signature = stage_file_rules.stage_signature(2, step, "input.mp4", str(tmp_path / "stage.mp4"))
    resume_state = stage_file_rules.empty_resume_state()

    assert stage_file_rules.safe_stage_name(step) == "01_super_resolution"
    assert '"stage": 2' in signature
    assert '"input":' in signature
    assert resume_state.start_source_frame == 0
    assert resume_state.completed_output_frames == 0
    assert resume_state.completed_segments == []
