from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_context import (
    StreamingPipelineContext,
    StreamingPipelinePreflight,
)


def test_streaming_pipeline_contexts_are_frozen_and_preserve_runtime_references(tmp_path) -> None:
    stage_plan = StagePlan(
        pre_steps=[],
        interpolation_step=None,
        post_steps=[],
        total_encoded_frames=4,
    )
    video_info = {"source_fps": 24.0, "source_frames": 4}
    preflight = StreamingPipelinePreflight(
        video_info=video_info,
        stage_plan=stage_plan,
        signature="sig",
        config_snapshot={"workflow": {}},
        use_stage_file_pipeline=False,
        resume_source_frames=4,
        output_width=640,
        output_height=360,
        segment_frames=1000,
    )
    decode_config = {"mode": "software"}
    encode_config = {"codec": "libx264"}
    metrics = PipelineMetrics()
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    context = StreamingPipelineContext(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path=str(tmp_path / "input.mp4"),
        output_path=str(tmp_path / "out.mp4"),
        decode_config=decode_config,
        encode_config=encode_config,
        preflight=preflight,
        manifest=manifest,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        tensor_backend_name="onnx",
        progress_callbacks=[],
        output_fps=None,
        encode_progress_callback=None,
        metrics=metrics,
    )

    assert context.preflight is preflight
    assert context.preflight.video_info is video_info
    assert context.decode_config is decode_config
    assert context.encode_config is encode_config
    assert context.manifest is manifest
    assert context.metrics is metrics

    with pytest.raises(FrozenInstanceError):
        setattr(preflight, "segment_frames", 10)
    with pytest.raises(FrozenInstanceError):
        setattr(context, "output_path", "other.mp4")


def test_process_video_streaming_reuses_one_context_for_dispatch_and_finalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import app.processing.streaming.pipeline as pipeline_module

    preflight = StreamingPipelinePreflight(
        video_info={"source_fps": 24.0, "source_frames": 4},
        stage_plan=StagePlan(
            pre_steps=[],
            interpolation_step=None,
            post_steps=[],
            total_encoded_frames=4,
        ),
        signature="sig",
        config_snapshot={"workflow": {}},
        use_stage_file_pipeline=False,
        resume_source_frames=4,
        output_width=640,
        output_height=360,
        segment_frames=1000,
    )
    manifest = SegmentManifest(str(tmp_path / "out.mp4"))
    resume_state = ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[])
    observed_contexts: list[StreamingPipelineContext] = []

    monkeypatch.setattr(
        pipeline_module,
        "build_streaming_pipeline_preflight",
        lambda **_kwargs: preflight,
    )
    monkeypatch.setattr(
        pipeline_module,
        "prepare_streaming_manifest",
        lambda **_kwargs: (manifest, resume_state),
    )

    def run_streaming_pipeline(*, context: StreamingPipelineContext) -> int:
        observed_contexts.append(context)
        return 4

    def finalize_streaming_output(
        *,
        context: StreamingPipelineContext,
        completed_output_frames: int,
    ) -> dict[str, object]:
        observed_contexts.append(context)
        return {"processed_frames": completed_output_frames}

    monkeypatch.setattr(pipeline_module, "run_streaming_pipeline", run_streaming_pipeline)
    monkeypatch.setattr(pipeline_module, "finalize_streaming_output", finalize_streaming_output)

    decode_config = {"mode": "software"}
    encode_config = {"codec": "libx264"}
    metrics = PipelineMetrics()
    result = pipeline_module.process_video_streaming(
        ffmpeg=object(),  # type: ignore[arg-type]
        input_path=str(tmp_path / "input.mp4"),
        output_path=str(tmp_path / "out.mp4"),
        decode_config=decode_config,
        encode_config=encode_config,
        workflow_config={},
        output_config={},
        processing_steps=[],
        tensor_backend_name="onnx",
        progress_callbacks=[],
        metrics=metrics,
    )

    assert result == {"processed_frames": 4}
    assert len(observed_contexts) == 2
    assert observed_contexts[0] is observed_contexts[1]
    assert observed_contexts[0].decode_config is decode_config
    assert observed_contexts[0].encode_config is encode_config
    assert observed_contexts[0].preflight is preflight
    assert observed_contexts[0].manifest is manifest
    assert observed_contexts[0].metrics is metrics
