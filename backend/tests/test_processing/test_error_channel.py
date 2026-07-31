from __future__ import annotations

import threading

from app.processing.streaming.error_channel import create_error_queue, report_first_error, take_first_error


def test_first_error_channel_is_bounded_and_never_blocks_later_producers() -> None:
    error_queue = create_error_queue()
    stop_event = threading.Event()
    first = RuntimeError("first failure")

    assert report_first_error(error_queue, stop_event, first) is True
    results: list[bool] = []
    producers = [
        threading.Thread(
            target=lambda index=index: results.append(
                report_first_error(error_queue, stop_event, RuntimeError(f"later failure {index}"))
            )
        )
        for index in range(100)
    ]
    for producer in producers:
        producer.start()
    for producer in producers:
        producer.join(timeout=1)

    assert all(not producer.is_alive() for producer in producers)
    assert results == [False] * len(producers)
    assert error_queue.maxsize == 1
    assert error_queue.qsize() == 1
    assert take_first_error(error_queue) is first
    assert take_first_error(error_queue) is None
    assert stop_event.is_set()
