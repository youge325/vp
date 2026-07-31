"""Frame-sequence PaddleGAN video super-resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.algorithms.paddle.paddlegan_vsr.runner import PaddleGanVsrRunner
from app.catalog.paddlegan_models import PADDLEGAN_VSR_SPECS


class PaddleGanVideoSuperResolution:
    def __init__(self, *, sr_algorithm: str, num_frames: int, engine: str) -> None:
        self._algorithm_name = sr_algorithm
        if self._algorithm_name not in PADDLEGAN_VSR_SPECS:
            raise ValueError(f"Unknown PaddleGAN VSR algorithm: {self._algorithm_name}")
        self._num_frames = num_frames
        if self._num_frames < 1:
            raise ValueError("PaddleGAN VSR num_frames must be at least 1.")
        self._engine = engine
        self._runner: PaddleGanVsrRunner | None = None

    def _ensure_runner(self) -> PaddleGanVsrRunner:
        if self._runner is None:
            self._runner = PaddleGanVsrRunner(
                model_id=self._algorithm_name,
                num_frames=self._num_frames,
                engine=self._engine,
            )
        return self._runner

    def process_frame_sequence(
        self,
        frames: list[Any],
        *,
        progress_callback: Callable[[int, int], None] | None,
    ) -> list[Any]:
        return self._ensure_runner().process_frames(frames, progress_callback=progress_callback)
