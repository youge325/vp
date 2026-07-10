"""Segment writer lifecycle for the streaming encoder worker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from app.planning import ResumeState, SegmentManifest
from app.processing.streaming.encoder_segments import (
    make_segment_progress_callback,
    resolve_segment_output_frame_count,
)
from app.processing.streaming.metrics import PipelineMetrics
from app.utils.ffmpeg import FFmpegWrapper


class EncoderSegmentWriter:
    def __init__(
        self,
        *,
        ffmpeg: FFmpegWrapper,
        encode_config: dict[str, Any],
        manifest: SegmentManifest,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None,
        segment_frames: int,
        resume_state: ResumeState,
        output_path: str,
        encode_progress_callback: Callable[[int, float | None, float | None, float | None, str], None] | None,
        metrics: PipelineMetrics,
    ) -> None:
        self.ffmpeg = ffmpeg
        self.encode_config = encode_config
        self.manifest = manifest
        self.width = width
        self.height = height
        self.fps = fps
        self.output_fps = output_fps
        self.segment_frames = segment_frames
        self.encode_progress_callback = encode_progress_callback
        self.metrics = metrics
        self._extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
        self._writer: Any | None = None
        self._segment_index = len(resume_state.completed_segments) + 1
        self._current_segment_start = resume_state.completed_output_frames
        self._current_segment_input_frames = 0
        self._tmp_path = ""

    def write_frame(self, frame: Any) -> None:
        if self._writer is None:
            self._open_segment()
        assert self._writer is not None
        self._writer.write_frame(frame)
        self._current_segment_input_frames += 1
        self.metrics.record_processed_frames(1)

    def seal_if_ready(self, next_source_frame: int) -> bool:
        if self._writer is None or self._current_segment_input_frames < self.segment_frames:
            return False
        self._seal_segment(next_source_frame)
        return True

    def seal_remaining(self, next_source_frame: int) -> bool:
        if self._writer is None or self._current_segment_input_frames <= 0:
            return False
        self._seal_segment(next_source_frame)
        return True

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
        self._tmp_path = self.manifest.chunk_tmp_path(self._extension, index=self._segment_index)
        self._writer = self.ffmpeg.open_rawvideo_encoder(
            output_path=self._tmp_path,
            width=self.width,
            height=self.height,
            fps=self.fps,
            output_fps=self.output_fps,
            encode_config=self.encode_config,
            progress_callback=make_segment_progress_callback(
                self._current_segment_start,
                self.encode_progress_callback,
            ),
        )

    def _seal_segment(self, next_source_frame: int) -> None:
        assert self._writer is not None
        writer = self._writer
        tmp_path = self._tmp_path
        writer.close()
        try:
            segment_output_frames = resolve_segment_output_frame_count(
                self.ffmpeg,
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
        self.manifest.finalize_chunk(
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
