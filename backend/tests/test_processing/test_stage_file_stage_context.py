from __future__ import annotations

from app.planning import ProcessingStep, SegmentManifest
from app.planning.manifest import ResumeState, SegmentRecord
from app.processing.streaming.stage_file_stage_context import build_stage_file_stage_context


def test_stage_file_stage_context_uses_resume_state_for_final_stage(tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 4.0},
        stage_name="01_super_resolution",
    )
    manifest = SegmentManifest(str(tmp_path / "final.mp4"))
    completed_segments = [
        SegmentRecord(
            index=1,
            path="chunk-0001-out00000000-00000003-src00000004.mp4",
            start_output_frame=0,
            end_output_frame=3,
            frame_count=4,
            next_source_frame=4,
        )
    ]
    resume_state = ResumeState(start_source_frame=99, completed_output_frames=4, completed_segments=completed_segments)
    encode_config = {"container": "mp4", "keepAudio": True}

    context = build_stage_file_stage_context(
        is_final_stage=True,
        stage_position=2,
        step=step,
        stage_root=tmp_path / "stages",
        current_path="intermediate.mp4",
        current_frame_count=10,
        output_path=str(tmp_path / "final.mp4"),
        manifest=manifest,
        resume_state=resume_state,
        encode_config=encode_config,
        segment_frames=5,
        output_fps=48.0,
    )

    assert context.manifest is manifest
    assert context.output_path == str(tmp_path / "final.mp4")
    assert context.resume_state is resume_state
    assert context.start_frame == 10
    assert context.chunk_start_index == 2
    assert context.encode_output_fps == 48.0
    assert context.encode_config is encode_config


def test_stage_file_stage_context_prepares_intermediate_stage_manifest(tmp_path) -> None:
    step = ProcessingStep(
        algorithm_type="frame_interpolation",
        algorithm_kwargs={"multi": 2},
        stage_name="01 frame/interpolation",
    )
    final_manifest = SegmentManifest(str(tmp_path / "final.mp4"))
    final_resume_state = ResumeState(start_source_frame=3, completed_output_frames=7, completed_segments=[])
    encode_config = {"container": "mkv", "keepAudio": True}

    context = build_stage_file_stage_context(
        is_final_stage=False,
        stage_position=1,
        step=step,
        stage_root=tmp_path / "stages",
        current_path=str(tmp_path / "input.mp4"),
        current_frame_count=12,
        output_path=str(tmp_path / "final.mp4"),
        manifest=final_manifest,
        resume_state=final_resume_state,
        encode_config=encode_config,
        segment_frames=0,
        output_fps=60.0,
    )

    assert context.output_path == str(tmp_path / "stages" / "stage-01-01_frame_interpolation.mp4")
    assert context.manifest is not final_manifest
    assert context.manifest.output_path.name == "stage-01-01_frame_interpolation.mp4"
    assert context.manifest.manifest_path.is_file()
    assert context.resume_state.start_source_frame == 0
    assert context.resume_state.completed_output_frames == 0
    assert context.resume_state.completed_segments == []
    assert context.start_frame == 0
    assert context.chunk_start_index == 1
    assert context.encode_output_fps is None
    assert context.encode_config == {"container": "mkv", "keepAudio": False}
    assert encode_config == {"container": "mkv", "keepAudio": True}
