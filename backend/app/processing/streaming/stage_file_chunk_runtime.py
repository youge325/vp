"""Single chunk runtime for file-backed stage execution."""

from __future__ import annotations

import threading
from typing import Any

from app.processing.streaming.stage_file_chunk_encoding import encode_stage_worker_output
from app.processing.streaming.error_channel import create_error_queue, take_first_error
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.stage_worker_config import build_stage_worker_step
from app.processing.streaming.stage_worker_progress import StageProgressCallback
from app.processing.streaming.worker_plans import StageChunkPlan
from app.processing.streaming.worker_process_io import DecodedFrameWriterConfig
from app.processing.streaming.worker_processes import stage_worker_session


def run_stage_chunk_to_file(
    *,
    config: StageFileRuntimeConfig,
    output_path: str,
    chunk: StageChunkPlan,
    stage_total_frames: int,
) -> int:
    worker_config = StageWorkerConfig(
        stage=build_stage_worker_step(config.step),
        stage_index=config.stage_index,
        stage_total=config.stage_total,
        stage_name=config.step.stage_name or config.step.algorithm_type,
        input_width=config.input_width,
        input_height=config.input_height,
        output_width=config.output_width,
        output_height=config.output_height,
        input_frame_count=chunk.input_frame_count,
        tensor_backend_name=config.tensor_backend_name,
        output_frame_count=chunk.raw_output_frame_count,
        output_frame_offset=chunk.output_frame_offset,
    )
    error_queue = create_error_queue()
    stop_event = threading.Event()

    callbacks: list[StageProgressCallback | None] = []
    if config.progress_callback is not None:

        def adapt_progress(current: int, *_worker_progress: Any, **kwargs: Any) -> None:
            logical_start_frame = (
                chunk.input_start_frame if chunk.logical_start_frame is None else chunk.logical_start_frame
            )
            current_value = min(
                logical_start_frame + max(int(current), 0),
                stage_total_frames,
            )
            config.progress_callback(current_value, stage_total_frames, **kwargs)

        callbacks = [None] * config.stage_total
        callbacks[config.stage_index - 1] = adapt_progress

    try:
        with stage_worker_session(
            [worker_config],
            progress_callbacks=callbacks,
            error_queue=error_queue,
            stop_event=stop_event,
            worker_log_sink=config.worker_log_sink,
        ) as group:
            handle = group.handles[0]
            group.start_decoded_frame_writer(
                DecodedFrameWriterConfig(
                    ffmpeg=config.ffmpeg,
                    input_path=config.input_path,
                    decode_config=config.decode_config,
                    width=config.input_width,
                    height=config.input_height,
                    start_source_frame=chunk.input_start_frame,
                    frame_count=chunk.input_frame_count,
                    worker_stdin=handle.process.stdin,
                    error_queue=error_queue,
                    stop_event=stop_event,
                ),
                thread_name=f"vp-stage-file-decode-{config.stage_index}",
            )
            if handle.process.stdout is None:
                raise RuntimeError("Stage worker stdout is unavailable.")
            encoded_frames = encode_stage_worker_output(
                config=config,
                output_path=output_path,
                worker_stdout=handle.process.stdout,
                chunk=chunk,
            )
    except BaseException:
        stop_event.set()
        raise

    if error := take_first_error(error_queue):
        raise error
    return encoded_frames


__all__ = ["run_stage_chunk_to_file"]
