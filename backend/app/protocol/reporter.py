"""CLI-side progress reporter.

Bridges the streaming pipeline's progress callbacks to two sinks:

- ``ndjson.progress`` for the structured stdout stream consumed by the
  Tauri host
- a human-readable line on stderr prefixed with ``[VP_PROGRESS]`` that
  the desktop log panel renders as an in-place progress bar

Lives in :mod:`app.protocol` (not :mod:`app.cli`) because the streaming
pipeline drives it through ``encode_progress_callback`` — keeping it
outside ``cli/`` avoids a ``processing -> cli`` reverse dependency.
"""

from __future__ import annotations

import sys
import time

from app.processing.streaming.metrics import PipelineMetrics
from app.protocol import ndjson

TERMINAL_PROGRESS_PREFIX = "[VP_PROGRESS]"
TERMINAL_PROGRESS_BAR_WIDTH = 24


def emit_terminal(message: str) -> None:
    """Write a single terminal-visible line to stderr."""
    print(message, file=sys.stderr, flush=True)


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--:--"
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_progress_bar(current: int, total: int) -> str:
    if total <= 0:
        total = 1
    ratio = min(max(current / total, 0.0), 1.0)
    filled = round(ratio * TERMINAL_PROGRESS_BAR_WIDTH)
    return f"[{'#' * filled}{'-' * (TERMINAL_PROGRESS_BAR_WIDTH - filled)}]"


class CliProgressReporter:
    """Throttled progress reporter for CLI-driven runs.

    Phase C.1.3:reporter 现在维护一个 ``(stage_name, stage_index, stage_total)``
    元组,供 streaming pipeline 在切换阶段时调用 ``set_stage`` 更新。这修复
    了原来 ``stage_index`` 在 NDJSON 中永远是 1 的 bug——以前 ``process.py``
    给所有阶段同一份 callback,reporter 无从得知正在汇报的是哪个 stage。

    Phase D.2.3:reporter 可选持有一个 ``PipelineMetrics`` 引用,update 时
    把当前 snapshot 一并塞进 NDJSON ``progress`` 帧的 ``metrics`` 字段。
    metrics 由 pipeline 在构造 reporter 时注入,reporter 不主动创建。
    """

    def __init__(self, total_frames: int, metrics: PipelineMetrics | None = None) -> None:
        self.total_frames = max(int(total_frames), 1)
        self.current_frame = 0
        self.started_at = time.time()
        self._last_reported_percent = -1.0
        # Phase C.1.3: stage 上下文。默认为单阶段,避免老调用方未 set_stage
        # 时仍能拿到合理的 NDJSON 输出。
        self._stage_name = "Encoding"
        self._stage_index = 1
        self._stage_total = 1
        # Phase D.2.3:可选 metrics 引用。
        self._metrics = metrics

    def set_stage(self, name: str, index: int, total: int) -> None:
        """Switch the current stage label / index / total.

        Called by the streaming pipeline (via per-stage callback closures)
        before each batch of ``update()`` calls. Safe to call repeatedly;
        no IO happens here, the change just rides on the next ``update``.
        """
        self._stage_name = name or self._stage_name
        self._stage_index = max(int(index), 1)
        self._stage_total = max(int(total), 1)

    def update(
        self,
        current_frame: int,
        fps: float | None = None,
        speed: float | None = None,
        _out_time_seconds: float | None = None,
        progress_state: str = "continue",
    ) -> None:
        self.current_frame = max(self.current_frame, max(int(current_frame), 0))
        display_current = min(self.current_frame, self.total_frames)
        percent = min((display_current / self.total_frames) * 100, 100.0)

        # 节流：进度变化小于 1% 且不是结束时跳过，避免每帧都刷 stdout
        is_end = progress_state == "end"
        if not is_end and abs(percent - self._last_reported_percent) < 1.0:
            return
        self._last_reported_percent = percent

        eta_seconds = 0.0 if is_end else self._estimate_eta(display_current, fps)
        fps_text = f"{fps:5.1f} fps" if fps and fps > 0 else "--.- fps"
        speed_text = f"{speed:.2f}x" if speed and speed > 0 else "--.--x"
        emit_terminal(
            f"{TERMINAL_PROGRESS_PREFIX} "
            f"{format_progress_bar(display_current, self.total_frames)} "
            f"{percent:5.1f}% "
            f"{display_current}/{self.total_frames} "
            f"| {fps_text} "
            f"| {speed_text} "
            f"| ETA {format_eta(eta_seconds)}"
        )
        ndjson.progress(
            current=display_current,
            total=self.total_frames,
            percent=round(percent, 1),
            stage=self._stage_name,
            stage_index=self._stage_index,
            stage_total=self._stage_total,
            metrics=self._metrics.snapshot() if self._metrics is not None else None,
        )

    def finish(self, processed_frames: int) -> None:
        self.update(processed_frames, progress_state="end")

    def _estimate_eta(self, current_frame: int, fps: float | None) -> float | None:
        remaining_frames = max(self.total_frames - min(current_frame, self.total_frames), 0)
        if remaining_frames == 0:
            return 0.0
        if fps is not None and fps > 0:
            return remaining_frames / fps

        elapsed = max(time.time() - self.started_at, 0.001)
        observed_fps = current_frame / elapsed if current_frame > 0 else 0.0
        if observed_fps <= 0:
            return None
        return remaining_frames / observed_fps
