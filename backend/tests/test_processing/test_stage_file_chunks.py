from __future__ import annotations

from pathlib import Path

from app.planning import ProcessingStep, SegmentManifest
from app.processing.streaming import stage_file_chunks, stage_file_rules
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.worker_plans import StageChunkPlan


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

    monkeypatch.setattr(stage_file_chunks, "run_stage_chunk_to_file", fake_run_stage_chunk_to_file)

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

    segments = manifest.read_completed_segments()
    assert completed == 5
    assert calls == [(0, 2, 2), (2, 2, 2), (4, 1, 1)]
    assert [segment.frame_count for segment in segments] == [2, 2, 1]


def test_chunk_progress_adapter_offsets_interpolation_by_source_frame() -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 3},
        stage_name="01_frame_interpolation",
    )
    chunk = StageChunkPlan(
        input_start_frame=2,
        input_frame_count=3,
        logical_input_frame_count=2,
        raw_output_frame_count=7,
        written_output_frame_count=6,
        skip_output_frames=1,
    )
    calls = []
    adapter = stage_file_chunks.chunk_progress_adapter(
        step,
        chunk=chunk,
        total=10,
        callback=lambda current, total, **kwargs: calls.append((current, total, kwargs)),
    )

    adapter(3, 999, phase="stage")

    assert stage_file_chunks.stage_chunk_output_start(step, chunk) == 6
    assert calls == [(5, 10, {"phase": "stage"})]


def test_chunk_progress_adapter_offsets_non_interpolation_by_output_frame() -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0, "sr_algorithm": "ppmsvsr"},
        stage_name="01_super_resolution",
    )
    chunk = StageChunkPlan(
        input_start_frame=4,
        input_frame_count=2,
        logical_input_frame_count=2,
        raw_output_frame_count=2,
        written_output_frame_count=2,
    )
    calls = []
    adapter = stage_file_chunks.chunk_progress_adapter(
        step,
        chunk=chunk,
        total=10,
        callback=lambda current, total, **kwargs: calls.append((current, total, kwargs)),
    )

    adapter(3, 999, phase="stage")

    assert stage_file_chunks.stage_chunk_output_start(step, chunk) == 4
    assert calls == [(7, 10, {"phase": "stage"})]


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
