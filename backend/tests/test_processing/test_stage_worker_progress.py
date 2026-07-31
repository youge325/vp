from __future__ import annotations

import io
from contextlib import redirect_stderr

import pytest

from app.generated.protocol_constants import NDJSON_LINE_LIMIT_BYTES, STAGE_WORKER_EVENT_PREFIX
from app.generated.stage_worker_contracts import (
    BackendTaskErrorCode,
    StageWorkerConfig,
    StageWorkerErrorEvent,
    StageWorkerPaddleSuperResolutionStep,
    StageWorkerProgressEvent,
)
from app.processing.streaming.stage_worker_progress import (
    StageProgressState,
    emit_stage_event,
    progress_event,
    start_sequence_stage_heartbeat,
)


def _config() -> StageWorkerConfig:
    return StageWorkerConfig(
        stage=StageWorkerPaddleSuperResolutionStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr", "engine": "cuda", "num_frames": 5},
        ),
        stage_index=2,
        stage_total=3,
        stage_name="01_super_resolution",
        input_width=1,
        input_height=1,
        output_width=4,
        output_height=4,
        input_frame_count=5,
        tensor_backend_name="paddle",
        output_frame_count=5,
    )


def test_stage_worker_progress_emits_prefixed_json_event() -> None:
    stream = io.StringIO()

    with redirect_stderr(stream):
        emit_stage_event(
            StageWorkerProgressEvent(
                type="progress",
                stage_name="stage",
                stage_index=1,
                stage_total=1,
                current=1,
                total=1,
                heartbeat=False,
                force=False,
            )
        )

    line = stream.getvalue().strip()
    assert line.startswith(STAGE_WORKER_EVENT_PREFIX)
    payload = line[len(STAGE_WORKER_EVENT_PREFIX) :]
    parsed = StageWorkerProgressEvent.model_validate_json(payload)
    assert parsed.current == 1
    assert parsed.heartbeat is False
    assert parsed.force is False


def test_stage_worker_event_rejects_oversized_line_before_writing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    event = StageWorkerErrorEvent(
        type="error",
        code=BackendTaskErrorCode.PROCESS_FAILED,
        message="worker failed",
        details={"traceback": "界" * NDJSON_LINE_LIMIT_BYTES},
    )

    with pytest.raises(ValueError, match="Protocol line"):
        emit_stage_event(event)

    assert capsys.readouterr().err == ""


def test_stage_worker_progress_event_and_heartbeat_use_latest_state() -> None:
    assert progress_event(_config(), 4, 8, heartbeat=True, force=True).model_dump(
        by_alias=True, exclude_none=True, mode="json"
    ) == {
        "type": "progress",
        "stageName": "01_super_resolution",
        "stageIndex": 2,
        "stageTotal": 3,
        "current": 4,
        "total": 8,
        "heartbeat": True,
        "force": True,
    }

    events = []
    state = StageProgressState(current=2, total=5)
    stop_event, thread = start_sequence_stage_heartbeat(
        _config(),
        events.append,
        total=5,
        progress_state=state,
        heartbeat_seconds=0.01,
    )
    try:
        state.current = 4
        assert stop_event.wait(0.03) is False
    finally:
        stop_event.set()
        thread.join(timeout=1)

    heartbeat_events = [event for event in events if event.heartbeat is True]
    assert heartbeat_events
    assert heartbeat_events[-1].current == 4
    assert heartbeat_events[-1].total == 5
