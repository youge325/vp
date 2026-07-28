"""Segment writer lifecycle for the streaming encoder worker."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_segments import resolve_segment_output_frame_count
from app.utils.ffmpeg._progress import make_encode_progress_callback
from app.utils.ffmpeg.io import RawVideoWriter


class EncoderSegmentWriter:
    def __init__(self, config: EncoderRuntimeConfig) -> None:
        self._config = config
        self._extension = (
            os.path.splitext(config.output_path)[1] or f".{config.encode_config.get('container') or 'mp4'}"
        )
        self._writer: RawVideoWriter | None = None
        self._segment_index = len(config.resume_state.completed_segments) + 1
        self._current_segment_start = config.resume_state.completed_output_frames
        self._current_segment_input_frames = 0
        self._tmp_path = ""

    def write_frame(self, frame: np.ndarray) -> None:
        if self._writer is None:
            self._open_segment()
        assert self._writer is not None
        self._writer.write_frame(frame)
        self._current_segment_input_frames += 1
        self._config.metrics.record_processed_frames(1)

    def seal_if_ready(self, next_source_frame: int) -> None:
        if self._writer is None or self._current_segment_input_frames < self._config.segment_frames:
            return
        self._seal_segment(next_source_frame)

    def seal_remaining(self, next_source_frame: int) -> None:
        if self._writer is None or self._current_segment_input_frames <= 0:
            return
        self._seal_segment(next_source_frame)

    def discard_open_segment(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:  # pragma: no cover - cleanup best effort
                pass
            self._writer = None
        if self._tmp_path:
            try:
                Path(self._tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - cleanup best effort
                pass
            self._tmp_path = ""
        self._current_segment_input_frames = 0

    def _open_segment(self) -> None:
        config = self._config
        self._tmp_path = config.manifest.chunk_tmp_path(self._extension, index=self._segment_index)
        self._writer = config.ffmpeg.open_rawvideo_encoder(
            output_path=self._tmp_path,
            width=config.width,
            height=config.height,
            fps=config.fps,
            output_fps=config.output_fps,
            encode_config=config.encode_config,
            progress_callback=make_encode_progress_callback(
                config.encode_progress_callback,
                frame_offset=self._current_segment_start,
            ),
        )

    def _seal_segment(self, next_source_frame: int) -> None:
        assert self._writer is not None
        writer = self._writer
        tmp_path = self._tmp_path
        writer.close()
        try:
            segment_output_frames = resolve_segment_output_frame_count(
                self._config.ffmpeg,
                writer,
                tmp_path,
                fallback_frame_count=self._current_segment_input_frames,
            )
        finally:
            self._writer = None
        if segment_output_frames <= 0:
            Path(tmp_path).unlink(missing_ok=True)
            self._current_segment_input_frames = 0
            self._tmp_path = ""
            return
        self._config.manifest.finalize_chunk(
            tmp_path,
            index=self._segment_index,
            start_output_frame=self._current_segment_start,
            end_output_frame=self._current_segment_start + segment_output_frames - 1,
            next_source_frame=next_source_frame,
        )
        self._segment_index += 1
        self._current_segment_start += segment_output_frames
        self._current_segment_input_frames = 0
        self._tmp_path = ""


__all__ = ["EncoderSegmentWriter"]
