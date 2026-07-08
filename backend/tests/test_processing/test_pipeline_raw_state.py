from __future__ import annotations

from app.processing.streaming.pipeline_raw_state import create_raw_pipeline_state


def test_create_raw_pipeline_state_allocates_runtime_queues_and_stop_event() -> None:
    state = create_raw_pipeline_state()

    assert state.encode_queue.maxsize == 8
    assert state.encode_queue.empty() is True
    assert state.error_queue.empty() is True
    assert state.stop_event.is_set() is False


def test_create_raw_pipeline_state_allows_custom_encode_queue_size() -> None:
    state = create_raw_pipeline_state(encode_queue_size=2)

    assert state.encode_queue.maxsize == 2
