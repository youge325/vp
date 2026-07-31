"""CLI-side progress reporter.

Bridges the streaming pipeline's progress callbacks to two sinks:

- the typed ``ndjson.emit`` boundary for the structured stdout stream consumed by the
  Tauri host
- a human-readable line on stderr prefixed with ``[VP_PROGRESS]`` that
  the desktop log panel renders as an in-place progress bar

Lives in :mod:`app.protocol` (not :mod:`app.cli`) because the streaming
pipeline drives it through ``encode_progress_callback`` — keeping it
outside ``cli/`` avoids a ``processing -> cli`` reverse dependency.

The metrics type annotation uses a private structural ``Protocol`` instead
of importing ``app.processing.streaming.metrics.PipelineMetrics`` directly.
This keeps ``protocol`` as a leaf layer while avoiding a public interface
module that no caller needs to import.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Protocol

from app.generated.contracts import TaskProgressPayload
from app.generated.protocol_constants import BackendEnvelopeType, TERMINAL_PROGRESS_PREFIX
from app.protocol import ndjson

_TERMINAL_PROGRESS_BAR_WIDTH = 24


class _MetricsSnapshot(Protocol):
    def snapshot(self) -> dict[str, Any]: ...


def _emit_terminal(message: str) -> None:
    """Write a single terminal-visible line to stderr."""
    print(message, file=sys.stderr, flush=True)


def _format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--:--"
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_progress_bar(current: int, total: int) -> str:
    if total <= 0:
        total = 1
    ratio = min(max(current / total, 0.0), 1.0)
    filled = round(ratio * _TERMINAL_PROGRESS_BAR_WIDTH)
    return f"[{'#' * filled}{'-' * (_TERMINAL_PROGRESS_BAR_WIDTH - filled)}]"


class CliProgressReporter:
    """Throttled progress reporter for CLI-driven runs.

    Reporter 维护一个 ``(stage_name, stage_index, stage_total)``
    元组,供 streaming pipeline 在切换阶段时调用 ``set_stage`` 更新。这修复
    了原来 ``stage_index`` 在 NDJSON 中永远是 1 的 bug——以前 ``process.py``
    给所有阶段同一份 callback,reporter 无从得知正在汇报的是哪个 stage。

    Reporter 可选持有一个 ``PipelineMetrics`` 引用,update 时
    把当前 snapshot 一并塞进 NDJSON ``progress`` 帧的 ``metrics`` 字段。
    metrics 由 pipeline 在构造 reporter 时注入,reporter 不主动创建。

    ``metrics`` uses a structural protocol, so any object providing
    ``snapshot() -> dict`` can be injected without a reverse dependency on
    ``processing.streaming``.
    """

    def __init__(self, total_frames: int, metrics: _MetricsSnapshot | None = None) -> None:
        self.total_frames = max(int(total_frames), 1)
        self.current_frame = 0
        self.started_at = time.time()
        self._last_reported_percent_by_stage: dict[tuple[int, str], float] = {}
        # Stage 上下文默认为单阶段,避免调用方未 set_stage
        # 时仍能拿到合理的 NDJSON 输出。
        self._stage_name = "Encoding"
        self._stage_index = 1
        self._stage_total = 1
        self._stage_frame_total = self.total_frames
        self._stage_started_at = self.started_at
        self._stage_current_frames: dict[tuple[int, str], int] = {}
        self._stage_changed = True
        self._metrics = metrics

    def set_stage(self, name: str, index: int, total: int, *, total_frames: int | None = None) -> None:
        """Switch the current stage label / index / total.

        Called by the streaming pipeline (via per-stage callback closures)
        before each batch of ``update()`` calls. Safe to call repeatedly;
        no IO happens here, the change just rides on the next ``update``.
        """
        next_name = name or self._stage_name
        next_index = max(int(index), 1)
        next_total = max(int(total), 1)
        next_key = (next_index, next_name)
        if next_key != self._stage_key():
            self._stage_started_at = time.time()
            self._stage_changed = True
        self._stage_name = next_name
        self._stage_index = next_index
        self._stage_total = next_total
        if total_frames is not None:
            self._stage_frame_total = max(int(total_frames), 1)

    def update(
        self,
        current_frame: int,
        fps: float | None = None,
        speed: float | None = None,
        _out_time_seconds: float | None = None,
        progress_state: str = "continue",
        *,
        total_frames: int | None = None,
        force: bool = False,
        heartbeat: bool = False,
    ) -> None:
        if total_frames is not None:
            self._stage_frame_total = max(int(total_frames), 1)

        stage_key = self._stage_key()
        previous_stage_current = self._stage_current_frames.get(stage_key, 0)
        self.current_frame = max(previous_stage_current, max(int(current_frame), 0))
        self._stage_current_frames[stage_key] = self.current_frame

        display_total = max(int(self._stage_frame_total), 1)
        display_current = min(self.current_frame, display_total)
        percent = min((display_current / display_total) * 100, 100.0)

        # 节流：进度变化小于 1% 且不是结束时跳过，避免每帧都刷 stdout
        is_end = progress_state == "end"
        should_force = (
            force or heartbeat or self._stage_changed or display_current == 0 or display_current >= display_total
        )
        last_reported_percent = self._last_reported_percent_by_stage.get(stage_key, -1.0)
        if not should_force and not is_end and abs(percent - last_reported_percent) < 1.0:
            return
        self._last_reported_percent_by_stage[stage_key] = percent
        self._stage_changed = False

        effective_fps = self._effective_fps(display_current, fps)
        eta_seconds = 0.0 if is_end else self._estimate_eta(display_current, effective_fps)
        fps_text = f"{effective_fps:5.1f} fps" if effective_fps and effective_fps > 0 else "--.- fps"
        speed_text = f"{speed:.2f}x" if speed and speed > 0 else "--.--x"
        run_text = f" | RUN {_format_eta(time.time() - self._stage_started_at)}" if heartbeat else ""
        if display_current > 0 or is_end:
            _emit_terminal(
                f"{TERMINAL_PROGRESS_PREFIX} "
                f"[{self._stage_index}/{self._stage_total} {self._stage_name}] "
                f"{_format_progress_bar(display_current, display_total)} "
                f"{percent:5.1f}% "
                f"{display_current}/{display_total} "
                f"| {fps_text} "
                f"| {speed_text} "
                f"| ETA {_format_eta(eta_seconds)}"
                f"{run_text}"
            )
        metrics = self._metrics.snapshot() if self._metrics is not None else None
        ndjson.emit(
            BackendEnvelopeType.PROGRESS,
            TaskProgressPayload(
                current=display_current,
                total=display_total,
                percent=round(percent, 1),
                stage=self._stage_name,
                stage_index=self._stage_index,
                stage_total=self._stage_total,
                metrics=metrics or None,
            ),
        )

    def finish(self) -> None:
        self.update(self._stage_frame_total, progress_state="end", force=True)

    def _effective_fps(self, current_frame: int, fps: float | None) -> float | None:
        if fps is not None and fps > 0:
            return fps
        if current_frame <= 0:
            return None

        elapsed = max(time.time() - self._stage_started_at, 0.001)
        observed_fps = current_frame / elapsed
        return observed_fps if observed_fps > 0 else None

    def _estimate_eta(self, current_frame: int, fps: float | None) -> float | None:
        display_total = max(int(self._stage_frame_total), 1)
        remaining_frames = max(display_total - min(current_frame, display_total), 0)
        if remaining_frames == 0:
            return 0.0
        if fps is not None and fps > 0:
            return remaining_frames / fps
        return None

    def _stage_key(self) -> tuple[int, str]:
        return self._stage_index, self._stage_name
