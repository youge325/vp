"""Raw pipeline encoder thread lifecycle."""

from __future__ import annotations

import queue
import threading

from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_worker import run_encoder_worker
from app.processing.streaming.queues import EncodedFrame, SegmentBoundary, StreamEnd


def start_raw_encoder_thread(
    *,
    config: EncoderRuntimeConfig,
    encode_queue: queue.Queue[EncodedFrame | SegmentBoundary | StreamEnd | object],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> threading.Thread:
    encoder_thread = threading.Thread(
        target=run_encoder_worker,
        name="vp-encoder",
        kwargs={
            "config": config,
            "encode_queue": encode_queue,
            "error_queue": error_queue,
            "stop_event": stop_event,
        },
        daemon=True,
    )

    if config.encode_progress_callback is not None and config.resume_state.completed_output_frames > 0:
        config.encode_progress_callback(
            config.resume_state.completed_output_frames,
            None,
            None,
            None,
            "continue",
        )

    encoder_thread.start()
    return encoder_thread


__all__ = ["start_raw_encoder_thread"]
