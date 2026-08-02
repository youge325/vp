"""Pure temporal window planning shared by parent segmentation and VSR inference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _TemporalSlice:
    logical_start: int
    logical_count: int
    read_start: int
    read_count: int
    output_offset: int


def plan_temporal_slices(
    total_frames: int,
    *,
    logical_chunk_frames: int,
    context_frames: int,
) -> tuple[_TemporalSlice, ...]:
    total = max(int(total_frames), 0)
    chunk = max(int(logical_chunk_frames), 1)
    context = max(int(context_frames), 0)
    slices: list[_TemporalSlice] = []
    for logical_start in range(0, total, chunk):
        logical_count = min(chunk, total - logical_start)
        read_start = max(logical_start - context, 0)
        read_end = min(logical_start + logical_count + context, total)
        slices.append(
            _TemporalSlice(
                logical_start=logical_start,
                logical_count=logical_count,
                read_start=read_start,
                read_count=read_end - read_start,
                output_offset=logical_start - read_start,
            )
        )
    return tuple(slices)


__all__ = ["plan_temporal_slices"]
