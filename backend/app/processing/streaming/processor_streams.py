"""Compatibility exports for queue-driven processor stream loops."""

from __future__ import annotations

from app.processing.streaming.processor_stream_interpolated import process_interpolated_stream
from app.processing.streaming.processor_stream_io import (
    drain_decoded,
    emit_encoded_payload,
    emit_stream_end,
)
from app.processing.streaming.processor_stream_sequence import process_sequence_stream
from app.processing.streaming.processor_stream_single import process_single_frame_stream

__all__ = [
    "drain_decoded",
    "emit_encoded_payload",
    "emit_stream_end",
    "process_interpolated_stream",
    "process_sequence_stream",
    "process_single_frame_stream",
]
