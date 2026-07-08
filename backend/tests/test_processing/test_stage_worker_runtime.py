from __future__ import annotations

import io
import json
from types import SimpleNamespace

from app.planning import ProcessingStep
from app.processing.streaming.stage_worker_runtime import (
    STAGE_EVENT_PREFIX,
    StageProgressState,
    create_backend,
    emit_stage_event,
    progress_event,
    start_sequence_stage_heartbeat,
)


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        stage=ProcessingStep(
            algorithm_type="super_resolution",
            algorithm_kwargs={"sr_algorithm": "ppmsvsr"},
            stage_name="01_super_resolution",
        ),
        stage_index=2,
        stage_total=3,
        stage_name="01_super_resolution",
        tensor_backend_name="paddle",
    )


def test_emit_stage_event_writes_prefixed_json_event() -> None:
    stream = io.StringIO()

    emit_stage_event({"type": "progress", "current": 1}, stream=stream)

    line = stream.getvalue().strip()
    assert line.startswith(STAGE_EVENT_PREFIX)
    assert json.loads(line[len(STAGE_EVENT_PREFIX) :]) == {"type": "progress", "current": 1}


def test_progress_event_includes_stage_identity_and_optional_flags() -> None:
    event = progress_event(_config(), 4, 8, heartbeat=True, force=True)

    assert event == {
        "type": "progress",
        "stageName": "01_super_resolution",
        "stageIndex": 2,
        "stageTotal": 3,
        "current": 4,
        "total": 8,
        "heartbeat": True,
        "force": True,
    }


def test_start_sequence_stage_heartbeat_uses_latest_progress_state() -> None:
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

    heartbeat_events = [event for event in events if event.get("heartbeat") is True]
    assert heartbeat_events
    assert heartbeat_events[-1]["current"] == 4
    assert heartbeat_events[-1]["total"] == 5


def test_create_backend_skips_frame_filter_chain_and_uses_factory_for_tensor_stages() -> None:
    config = _config()
    frame_filter_config = SimpleNamespace(
        stage=ProcessingStep(
            algorithm_type="frame_filter_chain",
            algorithm_kwargs={},
            stage_name="01_frame_filter_chain",
        ),
        tensor_backend_name="pytorch",
    )
    calls = []

    assert create_backend(frame_filter_config, lambda name: calls.append(name)) is None
    assert create_backend(config, lambda name: {"backend": name}) == {"backend": "paddle"}
    assert calls == []
