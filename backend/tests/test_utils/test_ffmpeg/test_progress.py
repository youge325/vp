from __future__ import annotations

from app.utils.ffmpeg._progress import make_encode_progress_callback


def test_make_encode_progress_callback_maps_payload_with_frame_offset() -> None:
    calls: list[tuple[int, float | None, float | None, float | None, str]] = []
    callback = make_encode_progress_callback(lambda *args: calls.append(args), frame_offset=10)

    assert callback is not None
    callback({"frame": "3", "fps": 48.0, "speed": 1.25, "out_time_seconds": 2.5, "progress": "continue"})

    assert calls == [(13, 48.0, 1.25, 2.5, "continue")]


def test_make_encode_progress_callback_normalizes_missing_values() -> None:
    calls: list[tuple[int, float | None, float | None, float | None, str]] = []
    callback = make_encode_progress_callback(lambda *args: calls.append(args))

    assert callback is not None
    callback({})

    assert calls == [(0, None, None, None, "")]


def test_make_encode_progress_callback_returns_none_without_consumer() -> None:
    assert make_encode_progress_callback(None, frame_offset=10) is None
