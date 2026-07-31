"""Encode stage-worker stdout into a temporary chunk file."""

from __future__ import annotations

import time
from typing import BinaryIO

from app.generated.protocol_constants import TERMINATION_REAP_TIMEOUT_MS
from app.processing.streaming.encoder_segment_writer import EncoderWriterOwner
from app.processing.streaming.encoder_segments import resolve_segment_output_frame_count
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from app.processing.streaming.stage_worker_io import read_rgb_frame
from app.processing.streaming.worker_plans import StageChunkPlan
from app.utils.late_cleanup import late_cleanup_coordinator


def encode_stage_worker_output(
    *,
    config: StageFileRuntimeConfig,
    output_path: str,
    worker_stdout: BinaryIO,
    chunk: StageChunkPlan,
) -> int:
    writer = None
    writer_owner = EncoderWriterOwner()
    written_frames = 0
    try:
        writer = config.ffmpeg.open_rawvideo_encoder(
            output_path=output_path,
            width=config.output_width,
            height=config.output_height,
            fps=config.output_fps,
            output_fps=config.encode_output_fps,
            encode_config=config.encode_config,
        )
        if not writer_owner.attach(writer):  # pragma: no cover - no concurrent shutdown in this owner
            raise RuntimeError("Stage chunk writer was created after shutdown began.")
        active_writer = writer
        for raw_index in range(chunk.raw_output_frame_count):
            frame = read_rgb_frame(
                worker_stdout,
                width=config.output_width,
                height=config.output_height,
            )
            if frame is None:
                break
            if raw_index < chunk.skip_output_frames:
                continue
            active_writer.write_frame(frame)
            written_frames += 1
            config.metrics.record_processed_frames(1)
        active_writer.close()
        writer_owner.detach(active_writer)
        writer = None
        encoded_frames = resolve_segment_output_frame_count(
            config.ffmpeg,
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
            except BaseException:
                deadline = time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000
                if not writer_owner.terminate_and_reap(deadline=deadline):
                    late_cleanup_coordinator.submit(writer_owner)
            else:
                writer_owner.detach(writer)


__all__ = ["encode_stage_worker_output"]
