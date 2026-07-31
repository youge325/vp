"""Segment writer lifecycle for the streaming encoder worker."""

from __future__ import annotations

import os
from pathlib import Path
import threading

import numpy as np

from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_segments import resolve_segment_output_frame_count
from app.ports.media import RawVideoWriterPort


class EncoderWriterOwner:
    """Thread-safe ownership of the encoder's currently active FFmpeg writer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._writer: RawVideoWriterPort | None = None
        self._shutdown_deadline: float | None = None

    def attach(self, writer: RawVideoWriterPort) -> bool:
        with self._lock:
            deadline = self._shutdown_deadline
            if deadline is None:
                self._writer = writer
                return True
            self._writer = writer
        try:
            reaped = writer.terminate_and_reap(deadline=deadline)
        except BaseException:  # pragma: no cover - process adapter boundary
            reaped = False
        if reaped:
            self.detach(writer)
        return False

    def detach(self, writer: RawVideoWriterPort) -> None:
        with self._lock:
            if self._writer is writer:
                self._writer = None

    def terminate_and_reap(self, *, deadline: float) -> bool:
        with self._lock:
            self._shutdown_deadline = deadline
            writer = self._writer
        if writer is None:
            return True
        try:
            reaped = writer.terminate_and_reap(deadline=deadline)
        except BaseException:  # pragma: no cover - process adapter boundary
            reaped = False
        if reaped:
            self.detach(writer)
        return reaped

    def retry_cleanup(self, *, deadline: float) -> bool:
        return self.terminate_and_reap(deadline=deadline)


class EncoderSegmentWriter:
    def __init__(self, config: EncoderRuntimeConfig, writer_owner: EncoderWriterOwner) -> None:
        self._config = config
        self._writer_owner = writer_owner
        self._extension = (
            os.path.splitext(config.output_path)[1] or f".{config.encode_config.get('container') or 'mp4'}"
        )
        self._writer: RawVideoWriterPort | None = None
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
        close_error: BaseException | None = None
        if self._writer is not None:
            writer = self._writer
            try:
                writer.close()
            except BaseException as exc:  # pragma: no cover - process adapter boundary
                close_error = exc
            else:
                self._writer_owner.detach(writer)
            self._writer = None
        if self._tmp_path:
            try:
                Path(self._tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - cleanup best effort
                pass
            self._tmp_path = ""
        self._current_segment_input_frames = 0
        if close_error is not None:
            raise close_error

    def _open_segment(self) -> None:
        config = self._config
        self._tmp_path = config.manifest.workspace.chunk_tmp_path(self._extension, index=self._segment_index)
        writer = config.ffmpeg.open_rawvideo_encoder(
            output_path=self._tmp_path,
            width=config.width,
            height=config.height,
            fps=config.fps,
            output_fps=config.output_fps,
            encode_config=config.encode_config,
            progress_callback=config.encode_progress_callback,
            progress_frame_offset=self._current_segment_start,
        )
        if not self._writer_owner.attach(writer):
            raise RuntimeError("Encoder writer was created after shutdown began.")
        self._writer = writer

    def _seal_segment(self, next_source_frame: int) -> None:
        assert self._writer is not None
        writer = self._writer
        tmp_path = self._tmp_path
        try:
            writer.close()
        except BaseException:
            self._writer = None
            raise
        else:
            self._writer_owner.detach(writer)
            self._writer = None
        segment_output_frames = resolve_segment_output_frame_count(
            self._config.ffmpeg,
            writer,
            tmp_path,
            fallback_frame_count=self._current_segment_input_frames,
        )
        if segment_output_frames <= 0:
            Path(tmp_path).unlink(missing_ok=True)
            self._current_segment_input_frames = 0
            self._tmp_path = ""
            return
        self._config.manifest.workspace.finalize_chunk(
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
