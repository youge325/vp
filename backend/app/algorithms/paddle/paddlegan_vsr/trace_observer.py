"""Optional PaddleGAN execution tracing isolated from sequence scheduling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from app.algorithms.paddle.paddlegan_vsr.tensor_codec import shape_list

_TRACE_ENV_VAR = "VP_PADDLEGAN_VSR_TRACE_PATH"


class PaddleGanTraceObserver:
    """Collect chunk shapes and memory metrics when an explicit trace path is set."""

    def __init__(self, path: Path | None):
        self._path = path
        self._chunks: list[dict[str, Any]] = []
        self._started_at = 0.0

    @classmethod
    def from_environment(cls) -> "PaddleGanTraceObserver":
        value = os.environ.get(_TRACE_ENV_VAR)
        return cls(Path(value) if value else None)

    def begin(self, paddle: Any) -> None:
        if self._path is None:
            return
        self._started_at = time.time()
        _reset_paddle_peak(paddle)

    def record_chunk(self, paddle: Any, *, tensor: Any, output: Any, frame_count: int) -> None:
        if self._path is None:
            return
        _sync_paddle(paddle)
        self._chunks.append(
            {
                "chunkFrameCount": frame_count,
                "inputShape": shape_list(tensor),
                "outputShape": shape_list(output),
            }
        )

    def finish(
        self,
        paddle: Any,
        *,
        model_id: str,
        sequence_mode: str,
        configured_num_frames: int,
        input_frame_count: int,
        output_frame_count: int,
    ) -> None:
        if self._path is None:
            return
        payload = {
            "event": "process_frames",
            "modelId": model_id,
            "sequenceMode": sequence_mode,
            "configuredNumFrames": configured_num_frames,
            "inputFrameCount": input_frame_count,
            "outputFrameCount": output_frame_count,
            "chunks": self._chunks,
            "elapsedSeconds": round(time.time() - self._started_at, 6),
            **_paddle_memory_snapshot(paddle),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _reset_paddle_peak(paddle: Any) -> None:
    for name in ("reset_max_memory_reserved", "reset_max_memory_allocated"):
        fn = getattr(getattr(paddle.device, "cuda", None), name, None)
        if callable(fn):
            fn()


def _paddle_memory_snapshot(paddle: Any) -> dict[str, int | None]:
    _sync_paddle(paddle)

    def call(name: str) -> int | None:
        fn = getattr(getattr(paddle.device, "cuda", None), name, None)
        if not callable(fn):
            return None
        return int(fn())

    return {
        "maxMemoryReservedBytes": call("max_memory_reserved"),
        "maxMemoryAllocatedBytes": call("max_memory_allocated"),
    }


def _sync_paddle(paddle: Any) -> None:
    device_sync = getattr(getattr(paddle, "device", None), "synchronize", None)
    if callable(device_sync):
        device_sync()
        return
    cuda_sync = getattr(getattr(paddle.device, "cuda", None), "synchronize", None)
    if callable(cuda_sync):
        cuda_sync()


__all__ = ["PaddleGanTraceObserver"]
