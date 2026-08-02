from __future__ import annotations

from pathlib import Path
import time
from typing import Any

import numpy as np

from app.planning.processing_steps import ProcessingStep
from app.processing.streaming.metrics import PipelineMetrics
from app.processing.streaming.stage_file_runtime_config import StageFileRuntimeConfig
from .streaming_runtime import ignore_worker_log


class FakeRawVideoWriter:
    def __init__(
        self,
        output_path: str,
        *,
        payload: bytes,
        progress_callback: Any = None,
        progress_frame_offset: int = 0,
    ) -> None:
        self.output_path = output_path
        self.progress_callback = progress_callback
        self.progress_frame_offset = progress_frame_offset
        self.payload = payload
        self.frames: list[np.ndarray] = []
        self.output_frame_count = 0
        self.closed = False

    def write_frame(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def close(self) -> None:
        self.closed = True
        output = Path(self.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(self.payload)
        self.output_frame_count = len(self.frames)
        if self.progress_callback is not None:
            self.progress_callback(
                self.progress_frame_offset + self.output_frame_count,
                24.0,
                1.0,
                None,
                "end",
            )

    def terminate_and_reap(self, *, deadline: float) -> bool:
        assert deadline >= time.monotonic()
        self.closed = True
        return True


class FakeRawVideoMedia:
    def __init__(self, *, payload: bytes = b"segment") -> None:
        self.payload = payload
        self.writers: list[FakeRawVideoWriter] = []
        self.encoder_dimensions: list[tuple[int, int]] = []

    @property
    def writer(self) -> FakeRawVideoWriter | None:
        return self.writers[-1] if self.writers else None

    def open_rawvideo_encoder(
        self,
        *,
        output_path: str,
        width: int | None = None,
        height: int | None = None,
        progress_callback: Any = None,
        progress_frame_offset: int = 0,
        **_kwargs: Any,
    ) -> FakeRawVideoWriter:
        if width is not None and height is not None:
            self.encoder_dimensions.append((width, height))
        writer = FakeRawVideoWriter(
            output_path,
            payload=self.payload,
            progress_callback=progress_callback,
            progress_frame_offset=progress_frame_offset,
        )
        self.writers.append(writer)
        return writer

    def get_frame_count(self, _path: str) -> int:
        return 0


def frame(value: int) -> np.ndarray:
    return np.full((1, 1, 3), value, dtype=np.uint8)


def make_stage_file_runtime_config(
    ffmpeg: Any,
    metrics: PipelineMetrics,
    *,
    step: ProcessingStep | None = None,
    progress_callback: Any = None,
) -> StageFileRuntimeConfig:
    resolved_step = step or ProcessingStep(
        algorithm_type="super_resolution",
        algorithm_kwargs={"scale_factor": 1.0, "sr_algorithm": "test-onnx"},
        stage_name="01_super_resolution",
    )
    return StageFileRuntimeConfig(
        ffmpeg=ffmpeg,
        input_path="input.mp4",
        decode_config={},
        encode_config={"container": "mp4"},
        step=resolved_step,
        stage_index=1,
        stage_total=1,
        tensor_backend_name="paddle",
        progress_callback=progress_callback,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        output_fps=24.0,
        encode_output_fps=None,
        metrics=metrics,
        worker_log_sink=ignore_worker_log,
    )
