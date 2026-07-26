from __future__ import annotations

from typing import Any

import pytest

from app.errors import ResumeConflictError
from app.planning import ResumeState, SegmentManifest, StagePlan
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.pipeline_context import (
    StreamingPipelineContext,
    StreamingPipelinePreflight,
)
from app.processing.streaming.pipeline_lifecycle import (
    emit_resume_status_event,
    finalize_streaming_output,
    prepare_streaming_manifest,
)


class _FakeFFmpeg:
    def __init__(self, frame_count: int | None) -> None:
        self.frame_count = frame_count
        self.counted_path: str | None = None

    def get_frame_count(self, path: str) -> int | None:
        self.counted_path = path
        return self.frame_count


def _context(
    tmp_path,
    *,
    ffmpeg: Any,
    manifest: SegmentManifest,
    encode_config: dict[str, Any],
) -> StreamingPipelineContext:
    stage_plan = StagePlan(
        pre_steps=[],
        interpolation_step=None,
        post_steps=[],
        total_encoded_frames=12,
    )
    return StreamingPipelineContext(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "input.mp4"),
        output_path=str(manifest.output_path),
        decode_config={},
        encode_config=encode_config,
        preflight=StreamingPipelinePreflight(
            video_info={"source_fps": 24.0, "source_frames": 12},
            stage_plan=stage_plan,
            signature="sig",
            config_snapshot={},
            use_stage_file_pipeline=False,
            resume_source_frames=12,
            output_width=1,
            output_height=1,
            segment_frames=1000,
        ),
        manifest=manifest,
        resume_state=ResumeState(start_source_frame=0, completed_output_frames=0, completed_segments=[]),
        tensor_backend_name="onnx",
        progress_callbacks=[],
        output_fps=None,
        encode_progress_callback=None,
        metrics=PipelineMetrics(),
    )


def test_prepare_streaming_manifest_raises_resume_conflict_for_existing_final_output(tmp_path) -> None:
    output_path = tmp_path / "out.mp4"
    output_path.write_bytes(b"existing")

    with pytest.raises(ResumeConflictError) as exc_info:
        prepare_streaming_manifest(
            output_path=str(output_path),
            signature="sig",
            config_snapshot={"input": "video.mp4"},
            resume_mode="auto",
        )

    exc = exc_info.value
    assert exc.output_path == str(output_path.resolve())
    assert exc.completed_chunks == 0
    assert exc.completed_output_frames == 0
    assert exc.sidecar_signature_match is False


def test_emit_resume_status_event_uses_existing_ndjson_payload(monkeypatch) -> None:
    events: list[dict[str, object]] = []
    state = ResumeState(
        start_source_frame=12,
        completed_output_frames=20,
        completed_segments=[object()],
    )
    monkeypatch.setattr(
        "app.processing.streaming.pipeline_lifecycle.ndjson.resume_status",
        lambda **kwargs: events.append(kwargs),
    )

    emit_resume_status_event(resume_state=state, total_output_frames=40)

    assert events == [
        {
            "resumed": True,
            "completed_chunks": 1,
            "completed_output_frames": 20,
            "start_source_frame": 12,
            "total_output_frames": 40,
        }
    ]


def test_finalize_streaming_output_cleans_sidecar_after_success_and_builds_result(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "out.mp4"
    manifest = SegmentManifest(str(output_path))
    manifest.sidecar_dir.mkdir(parents=True)
    calls: dict[str, object] = {}

    def fake_finalize(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(
        "app.processing.streaming.pipeline_lifecycle.finalize_segmented_output",
        fake_finalize,
    )
    ffmpeg = _FakeFFmpeg(frame_count=0)
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

    assert result == {
        "output_path": str(output_path),
        "processed_frames": 12,
        "audio_merged": False,
    }
    assert ffmpeg.counted_path == str(output_path)
    assert calls["manifest"] is manifest
    assert calls["strict_total_frames"] is True
    assert not manifest.sidecar_dir.exists()


def test_finalize_streaming_output_preserves_sidecar_when_finalize_fails(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "out.mp4"
    manifest = SegmentManifest(str(output_path))
    manifest.sidecar_dir.mkdir(parents=True)

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
                ffmpeg=_FakeFFmpeg(frame_count=0),
                manifest=manifest,
                encode_config={"keepAudio": True},
            ),
            completed_output_frames=12,
        )

    assert manifest.sidecar_dir.exists()
