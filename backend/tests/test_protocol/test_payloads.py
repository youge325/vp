from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.errors import TaskErrorCode
from app.generated.contracts import (
    BackendTaskErrorPayload,
    ResumeInspectionResult,
    ResumeStatusPayload,
    TaskCompletedPayload,
    TaskProgressPayload,
    VideoInfo,
)
from app.generated.protocol_constants import BackendEnvelopeType
from app.protocol import ndjson


def test_progress_payload_uses_contract_camel_case_shape() -> None:
    payload = TaskProgressPayload(
        current=12,
        total=24,
        percent=50.0,
        stage="Interpolation",
        stage_index=2,
        stage_total=3,
        metrics={"processedFrames": 12},
    )

    assert payload.model_dump(by_alias=True, mode="json") == {
        "current": 12,
        "total": 24,
        "percent": 50.0,
        "stage": "Interpolation",
        "stageIndex": 2,
        "stageTotal": 3,
        "metrics": {"processedFrames": 12},
    }


def test_progress_emitter_omits_absent_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    payload = TaskProgressPayload(
        current=1,
        total=10,
        percent=10.0,
        stage="Encoding",
        stage_index=1,
        stage_total=1,
        metrics=None,
    )

    ndjson.emit(BackendEnvelopeType.PROGRESS, payload)

    assert json.loads(capsys.readouterr().out) == {
        "type": "progress",
        "current": 1,
        "total": 10,
        "percent": 10.0,
        "stage": "Encoding",
        "stageIndex": 1,
        "stageTotal": 1,
    }


def test_completed_error_and_resume_payloads_keep_wire_shape() -> None:
    assert TaskCompletedPayload(
        output_path="D:/out.mp4",
        processed_frames=42,
        time_seconds=1.5,
    ).model_dump(by_alias=True, mode="json") == {
        "outputPath": "D:/out.mp4",
        "processedFrames": 42,
        "timeSeconds": 1.5,
    }

    assert BackendTaskErrorPayload(
        code=TaskErrorCode.INVALID_INPUT,
        message="missing input",
        details={},
    ).model_dump(by_alias=True, mode="json") == {
        "code": "invalid_input",
        "message": "missing input",
        "details": {},
    }

    assert ResumeStatusPayload(
        resumed=True,
        completed_chunks=2,
        completed_output_frames=100,
        start_source_frame=50,
        total_output_frames=240,
    ).model_dump(by_alias=True, mode="json") == {
        "resumed": True,
        "completedChunks": 2,
        "completedOutputFrames": 100,
        "startSourceFrame": 50,
        "totalOutputFrames": 240,
    }


def test_error_payload_can_preserve_empty_details() -> None:
    assert BackendTaskErrorPayload(
        code=TaskErrorCode.PROCESS_FAILED,
        message="boom",
        details={},
    ).model_dump(by_alias=True, mode="json") == {
        "code": "process_failed",
        "message": "boom",
        "details": {},
    }


def test_integer_metrics_remain_integers_on_the_wire() -> None:
    payload = TaskProgressPayload(
        current=1,
        total=2,
        percent=50,
        stage="Encoding",
        stage_index=1,
        stage_total=1,
        metrics={"queueDepth": 4},
    )
    wire = payload.model_dump(by_alias=True, mode="json")
    assert wire["metrics"]["queueDepth"] == 4
    assert isinstance(wire["metrics"]["queueDepth"], int)


def test_ndjson_emitter_uses_typed_payloads_without_changing_envelopes(capsys: pytest.CaptureFixture[str]) -> None:
    ndjson.emit(
        BackendEnvelopeType.PROGRESS,
        TaskProgressPayload(
            current=3,
            total=10,
            percent=30.0,
            stage="Preprocess",
            stage_index=1,
            stage_total=2,
            metrics=None,
        ),
    )
    ndjson.emit(
        BackendEnvelopeType.COMPLETED,
        TaskCompletedPayload(output_path="D:/done.mp4", processed_frames=10, time_seconds=2.25),
    )
    ndjson.emit(
        BackendEnvelopeType.ERROR,
        BackendTaskErrorPayload(
            code=TaskErrorCode.PROCESS_FAILED,
            message="boom",
            details={},
        ),
    )
    ndjson.emit(
        BackendEnvelopeType.RESUME_STATUS,
        ResumeStatusPayload(
            resumed=False,
            completed_chunks=0,
            completed_output_frames=0,
            start_source_frame=0,
            total_output_frames=10,
        ),
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines == [
        {
            "type": "progress",
            "current": 3,
            "total": 10,
            "percent": 30.0,
            "stage": "Preprocess",
            "stageIndex": 1,
            "stageTotal": 2,
        },
        {
            "type": "completed",
            "outputPath": "D:/done.mp4",
            "processedFrames": 10,
            "timeSeconds": 2.25,
        },
        {
            "type": "error",
            "code": "process_failed",
            "message": "boom",
            "details": {},
        },
        {
            "type": "resume_status",
            "resumed": False,
            "completedChunks": 0,
            "completedOutputFrames": 0,
            "startSourceFrame": 0,
            "totalOutputFrames": 10,
        },
    ]


def test_one_shot_emitters_require_generated_models(capsys: pytest.CaptureFixture[str]) -> None:
    ndjson.emit(
        BackendEnvelopeType.INFO,
        VideoInfo(fps=24.0, width=1920, height=1080, videoCodec="h264"),
    )
    ndjson.emit(
        BackendEnvelopeType.RESUME_INSPECTION,
        ResumeInspectionResult.model_validate(
            {
                "type": "resume_inspection",
                "pipeline_kind": "streaming",
                "outputPath": "D:/out.mp4",
                "input_path": "D:/in.mp4",
                "finalExists": False,
                "sidecarExists": False,
                "signatureMatch": False,
                "completedChunks": 0,
                "completedOutputFrames": 0,
                "nextSourceFrame": 0,
                "totalOutputFrames": 10,
            }
        ),
    )

    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {
            "type": "info",
            "fps": 24.0,
            "width": 1920,
            "height": 1080,
            "videoCodec": "h264",
        },
        {
            "type": "resume_inspection",
            "pipeline_kind": "streaming",
            "outputPath": "D:/out.mp4",
            "input_path": "D:/in.mp4",
            "finalExists": False,
            "sidecarExists": False,
            "signatureMatch": False,
            "completedChunks": 0,
            "completedOutputFrames": 0,
            "nextSourceFrame": 0,
            "totalOutputFrames": 10,
        },
    ]


def test_one_shot_generated_models_reject_invalid_or_unknown_values() -> None:
    with pytest.raises(ValidationError):
        VideoInfo.model_validate(
            {
                "fps": "not-a-number",
                "width": -1,
                "height": 1080,
                "videoCodec": "h264",
                "unexpected": True,
            }
        )


def test_ndjson_emitter_rejects_subclass_mirrors_of_generated_models() -> None:
    class MirroredVideoInfo(VideoInfo):
        pass

    with pytest.raises(TypeError, match="info requires VideoInfo"):
        ndjson.emit(
            BackendEnvelopeType.INFO,
            MirroredVideoInfo(fps=24.0, width=1920, height=1080, videoCodec="h264"),
        )


def test_typed_payloads_fail_fast_on_invalid_values() -> None:
    with pytest.raises(ValidationError):
        TaskProgressPayload(
            current=-1,
            total=10,
            percent=0.0,
            stage="Encoding",
            stage_index=1,
            stage_total=1,
        )

    with pytest.raises(ValidationError):
        BackendTaskErrorPayload(code="not_a_real_code", message="bad")

    with pytest.raises(ValidationError):
        TaskCompletedPayload(
            output_path="D:/out.mp4",
            processed_frames=1,
            time_seconds=1.0,
            unexpected=True,
        )


def test_emitter_rejects_payload_type_mismatch_before_writing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(TypeError, match="info requires VideoInfo"):
        ndjson.emit(
            BackendEnvelopeType.INFO,
            TaskCompletedPayload(
                output_path="D:/out.mp4",
                processed_frames=1,
                time_seconds=1.0,
            ),
        )

    assert capsys.readouterr().out == ""
