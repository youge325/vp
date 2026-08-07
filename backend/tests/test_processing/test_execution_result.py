from __future__ import annotations

import pytest

from app.processing.execution_result import resolve_final_output_frame_count


class _Probe:
    def __init__(self, value: int | Exception) -> None:
        self.value = value
        self.calls: list[str] = []

    def get_frame_count(self, input_path: str) -> int:
        self.calls.append(input_path)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (48, 48),
        (0, 24),
        (RuntimeError("ffprobe failed"), 24),
    ],
)
def test_final_output_frame_count_uses_one_soft_probe(value: int | Exception, expected: int) -> None:
    probe = _Probe(value)

    assert resolve_final_output_frame_count(probe, "output.mp4", fallback=24) == expected
    assert probe.calls == ["output.mp4"]


def test_final_output_frame_count_never_returns_a_negative_fallback() -> None:
    assert resolve_final_output_frame_count(_Probe(0), "output.mp4", fallback=-1) == 0
