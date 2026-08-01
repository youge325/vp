from __future__ import annotations

from typing import Any

import pytest

from app.errors import ResumeConflictError
from app.adapters.streaming_runtime import NdjsonResumeStatusSink
from app.generated.contracts import ResumeStatusPayload
from app.generated.protocol_constants import BackendEnvelopeType
from app.planning.manifest import ResumeState, SegmentManifest
from app.planning.stage_plan import StagePlan
from app.planning.stage_projection import StageProjection
from app.ports.media import VideoMetadata
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_context import (
    StreamingPipelineContext,
    StreamingPipelinePreflight,
)
from app.processing.streaming.pipeline_lifecycle import finalize_streaming_output, prepare_streaming_manifest
from tests.support.frame_count_probe import FakeFrameCountProbe
from tests.support.streaming_runtime import create_test_manifest, ignore_resume_status, ignore_worker_log


def _context(
    tmp_path,
    *,
    ffmpeg: Any,
    manifest: SegmentManifest,
    encode_config: dict[str, Any],
) -> StreamingPipelineContext:
    stage_plan = StagePlan(
        projection=StageProjection(()),
        source_frames=12,
        source_duration=0.5,
        output_fps=None,
    )
    return StreamingPipelineContext(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "input.mp4"),
        output_path=str(manifest.workspace.output_path),
        decode_config={},
        encode_config=encode_config,
        preflight=StreamingPipelinePreflight(
            video_info=VideoMetadata(
                width=1,
                height=1,
                source_fps=24.0,
                source_frames=12,
                duration=0.5,
                has_audio=False,
            ),
            stage_plan=stage_plan,
            signature="sig",
            config_snapshot={},
            output_width=1,
            output_height=1,
            segment_frames=1000,
        ),
        manifest=manifest,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        progress_callbacks=[],
        output_fps=None,
        encode_progress_callback=None,
        metrics=PipelineMetrics(),
        manifest_factory=create_test_manifest,
        resume_status_sink=ignore_resume_status,
        worker_log_sink=ignore_worker_log,
    )


def test_prepare_streaming_manifest_raises_resume_conflict_for_existing_final_output(tmp_path) -> None:
    output_path = tmp_path / "out.mp4"
    output_path.write_bytes(b"existing")

    with pytest.raises(ResumeConflictError) as exc_info:
        prepare_streaming_manifest(
            manifest=create_test_manifest(str(output_path)),
            signature="sig",
            config_snapshot={"input": "video.mp4"},
            resume_mode="auto",
        )

    exc = exc_info.value
    assert exc.output_path == str(output_path.resolve())
    assert exc.completed_chunks == 0
    assert exc.completed_output_frames == 0
    assert exc.sidecar_signature_match is False


def test_ndjson_resume_status_sink_uses_generated_payload(monkeypatch) -> None:
    events: list[tuple[BackendEnvelopeType, ResumeStatusPayload]] = []
    state = ResumeState(
        start_source_frame=12,
        completed_output_frames=20,
        completed_segments=[object()],
    )
    monkeypatch.setattr(
        "app.adapters.streaming_runtime.ndjson.emit",
        lambda event_type, payload: events.append((event_type, payload)),
    )

    NdjsonResumeStatusSink()(state, 40)

    assert events[0][0] is BackendEnvelopeType.RESUME_STATUS
    assert events[0][1].model_dump(mode="json") == {
        "resumed": True,
        "completed_chunks": 1,
        "completed_output_frames": 20,
        "start_source_frame": 12,
        "total_output_frames": 40,
    }


def test_ndjson_resume_status_sink_propagates_required_envelope_failure(monkeypatch) -> None:
    state = ResumeState(
        start_source_frame=0,
        completed_output_frames=0,
        completed_segments=[],
    )

    def fail_emit(*_args, **_kwargs) -> None:
        raise OSError("stdout closed")

    monkeypatch.setattr("app.adapters.streaming_runtime.ndjson.emit", fail_emit)

    with pytest.raises(OSError, match="stdout closed"):
        NdjsonResumeStatusSink()(state, 40)


def test_finalize_streaming_output_cleans_sidecar_after_success_and_builds_result(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output_path))
    manifest.workspace.sidecar_dir.mkdir(parents=True)
    calls: dict[str, object] = {}

    def fake_finalize(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_lifecycle.finalize_segmented_output",
        fake_finalize,
    )
    ffmpeg = FakeFrameCountProbe(frame_count=0)
    context = _context(
        tmp_path,
        ffmpeg=ffmpeg,
        manifest=manifest,
        encode_config={"keepAudio": False},
    )

    result = finalize_streaming_output(
        context=context,
        completed_output_frames=12,
    )

    assert result.output_path == str(output_path)
    assert result.processed_frames == 12
    assert ffmpeg.counted_path == str(output_path)
    assert calls["manifest"] is manifest
    assert calls["strict_total_frames"] is True
    assert not manifest.workspace.sidecar_dir.exists()


def test_finalize_streaming_output_preserves_sidecar_when_finalize_fails(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "out.mp4"
    manifest = create_test_manifest(str(output_path))
    manifest.workspace.sidecar_dir.mkdir(parents=True)

    def fail_finalize(**kwargs):
        del kwargs
        raise RuntimeError("concat failed")

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_lifecycle.finalize_segmented_output",
        fail_finalize,
    )

    with pytest.raises(RuntimeError, match="concat failed"):
        finalize_streaming_output(
            context=_context(
                tmp_path,
                ffmpeg=FakeFrameCountProbe(frame_count=0),
                manifest=manifest,
                encode_config={"keepAudio": True},
            ),
            completed_output_frames=12,
        )

    assert manifest.workspace.sidecar_dir.exists()
