"""Encode stage-worker stdout into a temporary chunk file."""

from __future__ import annotations

from typing import Any, BinaryIO

from app.processing.streaming.encoder_segments import resolve_segment_output_frame_count
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_worker import read_rgb_frame
from app.processing.streaming.worker_plans import StageChunkPlan


def encode_stage_worker_output(
    *,
    ffmpeg: Any,
    encode_config: dict[str, Any],
    output_path: str,
    worker_stdout: BinaryIO,
    chunk: StageChunkPlan,
    output_width: int,
    output_height: int,
    output_fps: float,
    encode_output_fps: float | None,
    metrics: PipelineMetrics,
) -> int:
    writer = None
    written_frames = 0
    try:
        writer = ffmpeg.open_rawvideo_encoder(
            output_path=output_path,
            width=output_width,
            height=output_height,
            fps=output_fps,
            output_fps=encode_output_fps,
            encode_config=encode_config,
        )
        active_writer = writer
        for raw_index in range(chunk.raw_output_frame_count):
            frame = read_rgb_frame(worker_stdout, width=output_width, height=output_height)
            if frame is None:
                break
            if raw_index < chunk.skip_output_frames:
                continue
            active_writer.write_frame(frame)
            written_frames += 1
            metrics.record_processed_frames(1)
        active_writer.close()
        writer = None
        encoded_frames = resolve_segment_output_frame_count(
            ffmpeg,
            active_writer,
            output_path,
            fallback_frame_count=written_frames,
        )
        if written_frames != chunk.written_output_frame_count:
            raise RuntimeError(
                "Stage chunk output frame count mismatch: "
                f"expected {chunk.written_output_frame_count}, got {written_frames}."
            )
        return encoded_frames
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass


__all__ = ["encode_stage_worker_output"]
