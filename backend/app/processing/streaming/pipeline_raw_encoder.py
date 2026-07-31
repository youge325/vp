"""Raw pipeline encoder thread lifecycle."""

from __future__ import annotations

import math
import queue
import threading
import time

from app.processing.streaming.encoder_runtime_config import EncoderRuntimeConfig
from app.processing.streaming.encoder_worker import run_encoder_worker
from app.processing.streaming.encoder_segment_writer import EncoderWriterOwner
from app.utils.late_cleanup import late_cleanup_coordinator
from app.processing.streaming.queues import EncodeQueue, _ENCODE_END, _queue_put_nowait


class RawEncoderOwner:
    """Own the encoder thread and the FFmpeg process it may block on."""

    def __init__(
        self,
        *,
        thread: threading.Thread,
        writer_owner: EncoderWriterOwner,
        encode_queue: EncodeQueue,
        stop_event: threading.Event,
    ) -> None:
        self._thread = thread
        self._writer_owner = writer_owner
        self._encode_queue = encode_queue
        self._stop_event = stop_event

    def finish(self, *, deadline: float) -> bool:
        _validate_deadline(deadline)
        remaining = max(deadline - time.monotonic(), 0.0)
        cleanup_reserve = min(1.0, remaining / 2)
        self._thread.join(timeout=max(remaining - cleanup_reserve, 0.0))
        if not self._thread.is_alive():
            return self._retain_until_clean(self._writer_owner.terminate_and_reap(deadline=deadline))
        return self.abort(deadline=deadline)

    def abort(self, *, deadline: float) -> bool:
        _validate_deadline(deadline)
        return self._retain_until_clean(self._abort_once(deadline=deadline))

    def retry_cleanup(self, *, deadline: float) -> bool:
        return self._abort_once(deadline=deadline)

    def _abort_once(self, *, deadline: float) -> bool:
        self._stop_event.set()
        _queue_put_nowait(self._encode_queue, _ENCODE_END)
        writer_reaped = self._writer_owner.terminate_and_reap(deadline=deadline)
        if not writer_reaped:
            return False
        self._thread.join(timeout=max(deadline - time.monotonic(), 0.0))
        return not self._thread.is_alive()

    def _retain_until_clean(self, cleanup_succeeded: bool) -> bool:
        if not cleanup_succeeded:
            late_cleanup_coordinator.submit(self)
        return cleanup_succeeded


def _validate_deadline(deadline: float) -> None:
    if not math.isfinite(deadline):
        raise ValueError("Encoder cleanup deadline must be finite.")


def start_raw_encoder_thread(
    *,
    config: EncoderRuntimeConfig,
    encode_queue: EncodeQueue,
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
) -> RawEncoderOwner:
    writer_owner = EncoderWriterOwner()
    encoder_thread = threading.Thread(
        target=run_encoder_worker,
        name="vp-encoder",
        kwargs={
            "config": config,
            "encode_queue": encode_queue,
            "error_queue": error_queue,
            "stop_event": stop_event,
            "writer_owner": writer_owner,
        },
        daemon=False,
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
    return RawEncoderOwner(
        thread=encoder_thread,
        writer_owner=writer_owner,
        encode_queue=encode_queue,
        stop_event=stop_event,
    )


__all__ = ["start_raw_encoder_thread"]
