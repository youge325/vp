from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.errors import TaskErrorCode
from app.protocol import ndjson
from app.protocol.payloads import (
    ResumeStatusPayload,
    TaskCompletedPayload,
    TaskErrorPayload,
    TaskProgressPayload,
)


def test_progress_payload_to_wire_uses_legacy_camel_case_shape() -> None:
    payload = TaskProgressPayload(
        current=12,
        total=24,
        percent=50.0,
        stage="Interpolation",
        stage_index=2,
        stage_total=3,
        metrics={"processedFrames": 12},
    )

    assert payload.to_wire() == {
        "current": 12,
        "total": 24,
        "percent": 50.0,
        "stage": "Interpolation",
        "stageIndex": 2,
        "stageTotal": 3,
        "metrics": {"processedFrames": 12},
    }


def test_progress_payload_omits_empty_metrics_like_old_emitter() -> None:
    payload = TaskProgressPayload(
        current=1,
        total=10,
        percent=10.0,
        stage="Encoding",
        stage_index=1,
        stage_total=1,
        metrics={},
    )

    assert payload.to_wire() == {
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
    ).to_wire() == {
        "outputPath": "D:/out.mp4",
        "processedFrames": 42,
        "timeSeconds": 1.5,
    }

    assert TaskErrorPayload(
        code=TaskErrorCode.INVALID_INPUT,
        message="missing input",
        details=None,
    ).to_wire() == {
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
    ).to_wire() == {
        "resumed": True,
        "completedChunks": 2,
        "completedOutputFrames": 100,
        "startSourceFrame": 50,
        "totalOutputFrames": 240,
    }


def test_ndjson_emitter_uses_typed_payloads_without_changing_envelopes(capsys: pytest.CaptureFixture[str]) -> None:
    ndjson.progress(
        current=3,
        total=10,
        percent=30.0,
        stage="Preprocess",
        stage_index=1,
        stage_total=2,
        metrics=None,
    )
    ndjson.completed(output_path="D:/done.mp4", processed_frames=10, time_seconds=2.25)
    ndjson.error(code=TaskErrorCode.PROCESS_FAILED, message="boom", details=None)
    ndjson.resume_status(
        resumed=False,
        completed_chunks=0,
        completed_output_frames=0,
        start_source_frame=0,
        total_output_frames=10,
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
        TaskErrorPayload(code="not_a_real_code", message="bad")

    with pytest.raises(ValidationError):
        TaskCompletedPayload(
            output_path="D:/out.mp4",
            processed_frames=1,
            time_seconds=1.0,
            unexpected=True,
        )
