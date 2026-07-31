"""Parent-side stage-worker process runtime helpers."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
from typing import Iterator, Sequence

from app.errors import ProcessError, TaskErrorCode
from app.generated.protocol_constants import (
    STAGE_WORKER_COMMAND,
    STAGE_WORKER_CONFIG_FLAG,
    STAGE_WORKER_SUBCOMMAND,
    STAGE_WORKER_TERMINATION_REAP_TIMEOUT_MS,
)
from app.generated.stage_worker_contracts import StageWorkerConfig
from app.processing.streaming.error_channel import create_error_queue, take_first_error
from app.processing.streaming.stage_worker_progress import StageProgressCallback
from app.processing.streaming.runtime_ports import WorkerLogSink
from app.utils.late_cleanup import late_cleanup_coordinator
from app.processing.streaming.worker_process_events import read_worker_stderr
from app.processing.streaming.worker_process_io import DecodedFrameWriter, DecodedFrameWriterConfig, close_pipe
from app.utils.subprocess_utils import hidden_subprocess_kwargs

_WORKER_REAP_TIMEOUT_SECONDS = STAGE_WORKER_TERMINATION_REAP_TIMEOUT_MS / 1000


@dataclass(slots=True)
class _WorkerHandle:
    process: subprocess.Popen[bytes]
    config: StageWorkerConfig
    stderr_tail: deque[str]


class _WorkerSpawnFailure(RuntimeError):
    def __init__(self, cause: BaseException, handles: Sequence[_WorkerHandle]) -> None:
        self.cause = cause
        self.handles = list(handles)
        super().__init__(str(cause))


def _spawn_stage_workers(
    configs: list[StageWorkerConfig],
    *,
    config_dir: Path,
) -> list[_WorkerHandle]:
    handles: list[_WorkerHandle] = []
    previous_stdout = None
    root = _backend_dir()

    try:
        for index, config in enumerate(configs):
            config_path = config_dir / f"stage-{index + 1:02d}.json"
            config_path.write_text(config.model_dump_json(by_alias=True, exclude_unset=True), encoding="utf-8")
            stdin = subprocess.PIPE if index == 0 else previous_stdout
            process = subprocess.Popen(
                [
                    sys.executable,
                    *STAGE_WORKER_COMMAND,
                    STAGE_WORKER_SUBCOMMAND,
                    STAGE_WORKER_CONFIG_FLAG,
                    str(config_path),
                ],
                cwd=str(root),
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **hidden_subprocess_kwargs(),
            )
            # Ownership begins as soon as Popen succeeds. Closing the previous
            # pipe and validating the new pipe can both raise; rollback must
            # still retain and reap this process.
            handle = _WorkerHandle(process=process, config=config, stderr_tail=deque())
            handles.append(handle)
            if previous_stdout is not None:
                previous_stdout.close()
            if process.stdout is None:
                raise RuntimeError("Unable to capture stage-worker stdout.")
            previous_stdout = process.stdout
    except BaseException as exc:
        raise _WorkerSpawnFailure(exc, handles) from exc

    return handles


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def _terminate_and_reap(
    handles: list[_WorkerHandle],
    *,
    deadline: float | None = None,
) -> tuple[BaseException, ...]:
    """Best-effort bounded rollback for every process already owned by the group."""
    cleanup_deadline = deadline or (time.monotonic() + _WORKER_REAP_TIMEOUT_SECONDS)
    failures: list[BaseException] = []
    for handle in reversed(handles):
        try:
            process = handle.process
            if process.poll() is None:
                process.terminate()
            try:
                remaining = max(cleanup_deadline - time.monotonic(), 0.0)
                process.wait(timeout=remaining / 2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=max(cleanup_deadline - time.monotonic(), 0.0))
        except BaseException as exc:  # pragma: no cover - defensive process boundary
            failures.append(exc)
    return tuple(failures)


def _close_worker_pipes(handles: Sequence[_WorkerHandle]) -> None:
    for handle in handles:
        close_pipe(handle.process.stdin)
        close_pipe(handle.process.stdout)
        close_pipe(getattr(handle.process, "stderr", None))


def _join_reader_threads(
    threads: Sequence[threading.Thread],
    *,
    deadline: float,
) -> tuple[str, ...]:
    alive: list[str] = []
    for thread in threads:
        thread.join(timeout=max(deadline - time.monotonic(), 0.0))
        if thread.is_alive():
            alive.append(thread.name)
    return tuple(alive)


class _StageWorkerCleanupError(RuntimeError):
    """Cleanup failure that retains the process/thread owner for diagnosis or retry."""

    def __init__(self, owner: StageWorkerGroup, failures: Sequence[BaseException]) -> None:
        self.owner = owner
        summary = "; ".join(str(failure) for failure in failures)
        super().__init__(f"Stage-worker cleanup failed: {summary}")


@dataclass(slots=True)
class StageWorkerGroup:
    """Own all worker processes, stderr readers, rollback, and bounded cleanup."""

    handles: list[_WorkerHandle]
    stderr_threads: list[threading.Thread]
    decoded_frame_writers: list[DecodedFrameWriter]
    stop_event: threading.Event
    error_queue: queue.Queue[BaseException] = field(default_factory=create_error_queue)
    _cleanup_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def start(
        cls,
        configs: list[StageWorkerConfig],
        *,
        config_dir: Path,
        progress_callbacks: Sequence[StageProgressCallback | None],
        error_queue: queue.Queue[BaseException],
        stop_event: threading.Event,
        worker_log_sink: WorkerLogSink,
    ) -> StageWorkerGroup:
        try:
            handles = _spawn_stage_workers(configs, config_dir=config_dir)
        except _WorkerSpawnFailure as failure:
            stop_event.set()
            owner = cls(failure.handles, [], [], stop_event, error_queue)
            try:
                owner.close()
            except _StageWorkerCleanupError as cleanup_error:
                raise cleanup_error from failure.cause
            raise failure.cause
        threads = [
            threading.Thread(
                target=read_worker_stderr,
                name=f"vp-stage-worker-stderr-{handle.config.stage_index}",
                args=(handle, progress_callbacks, error_queue, stop_event, worker_log_sink),
                daemon=False,
            )
            for handle in handles
        ]
        started_threads: list[threading.Thread] = []
        try:
            for thread in threads:
                thread.start()
                started_threads.append(thread)
        except BaseException as exc:
            stop_event.set()
            reader_deadline = time.monotonic() + _WORKER_REAP_TIMEOUT_SECONDS
            cleanup_errors = _terminate_and_reap(handles, deadline=reader_deadline)
            stuck_readers = _join_reader_threads(started_threads, deadline=reader_deadline)
            if not stuck_readers and not cleanup_errors:
                _close_worker_pipes(handles)
            failures: list[BaseException] = list(cleanup_errors)
            failures.extend(
                RuntimeError(f"Stage-worker stderr reader missed rollback deadline: {thread_name}")
                for thread_name in stuck_readers
            )
            if failures:
                owner = cls(handles, started_threads, [], stop_event, error_queue)
                late_cleanup_coordinator.submit(owner)
                raise _StageWorkerCleanupError(owner, [exc, *failures]) from exc
            raise
        return cls(handles, threads, [], stop_event, error_queue)

    def start_decoded_frame_writer(self, config: DecodedFrameWriterConfig, *, thread_name: str) -> None:
        writer = DecodedFrameWriter(config, thread_name=thread_name)
        writer.start()
        self.decoded_frame_writers.append(writer)

    def close(self) -> None:
        cleanup_failures = self._cleanup_once()
        if not cleanup_failures:
            return
        late_cleanup_coordinator.submit(self)
        raise _StageWorkerCleanupError(self, cleanup_failures)

    def finish_successfully(self) -> None:
        """Confirm writers, workers, stderr readers, and final stdout all finish cleanly."""
        deadline = time.monotonic() + _WORKER_REAP_TIMEOUT_SECONDS
        self._raise_first_error()
        for writer in self.decoded_frame_writers:
            if not writer.join_until(deadline=deadline):
                self._raise_first_error()
                raise RuntimeError("Stage worker decoder did not finish before the success deadline.")
            if not writer.request_stop(deadline=deadline):
                self._raise_first_error()
                raise RuntimeError("Stage worker decoder ownership was not reaped before the success deadline.")
            if writer.cleanup_error is not None:
                self._raise_first_error()
                raise RuntimeError("Stage worker decoder failed during graceful cleanup.") from writer.cleanup_error

        return_codes: list[int] = []
        for handle in self.handles:
            try:
                return_codes.append(handle.process.wait(timeout=max(deadline - time.monotonic(), 0.0)))
            except subprocess.TimeoutExpired as exc:
                self._raise_first_error()
                raise RuntimeError("Stage worker did not exit before the success deadline.") from exc

        stuck_readers = _join_reader_threads(self.stderr_threads, deadline=deadline)
        if stuck_readers:
            self._raise_first_error()
            raise RuntimeError(f"Stage worker stderr readers did not finish: {', '.join(stuck_readers)}")
        self._raise_first_error()
        if return_codes != [0] * len(self.handles):
            failures = [
                {
                    "stage": handle.config.stage_name,
                    "return_code": return_code,
                    "stderr": list(handle.stderr_tail),
                }
                for handle, return_code in zip(self.handles, return_codes, strict=True)
                if return_code != 0
            ]
            raise ProcessError(
                TaskErrorCode.PROCESS_FAILED,
                "Stage worker exited with a non-zero status.",
                details={"workers": failures},
            )

        final_stdout = self.handles[-1].process.stdout if self.handles else None
        if final_stdout is not None and final_stdout.read(1):
            raise RuntimeError("Stage worker produced more output bytes than the projected frame count.")
        _close_worker_pipes(self.handles)

    def _raise_first_error(self) -> None:
        if error := take_first_error(self.error_queue):
            raise error

    def retry_cleanup(self, *, deadline: float) -> bool:
        return not self._cleanup_once(deadline=deadline)

    def _cleanup_once(self, *, deadline: float | None = None) -> tuple[BaseException, ...]:
        with self._cleanup_lock:
            return self._cleanup_once_locked(
                cleanup_deadline=deadline or (time.monotonic() + _WORKER_REAP_TIMEOUT_SECONDS)
            )

    def _cleanup_once_locked(self, *, cleanup_deadline: float) -> tuple[BaseException, ...]:
        join_reserve = min(1.0, _WORKER_REAP_TIMEOUT_SECONDS / 2)
        process_deadline = cleanup_deadline - join_reserve
        worker_deadline = time.monotonic() + max(process_deadline - time.monotonic(), 0.0) / 2
        cleanup_failures: list[BaseException] = []
        for writer in self.decoded_frame_writers:
            writer.signal_stop()
        for cleanup_error in _terminate_and_reap(self.handles, deadline=worker_deadline):
            self.stop_event.set()
            cleanup_failures.append(cleanup_error)
        for writer in self.decoded_frame_writers:
            if writer.request_stop(deadline=process_deadline):
                continue
            self.stop_event.set()
            cleanup_failures.append(
                ProcessError(
                    TaskErrorCode.PROCESS_FAILED,
                    "Stage worker decoded-frame source did not exit before the cleanup deadline.",
                    details={"thread": writer.thread_name},
                )
            )
        writers_joined = True
        for writer in self.decoded_frame_writers:
            if writer.join_until(deadline=cleanup_deadline):
                continue
            writers_joined = False
            self.stop_event.set()
            cleanup_failures.append(
                ProcessError(
                    TaskErrorCode.PROCESS_FAILED,
                    "Stage worker decoded-frame writer did not exit before the cleanup deadline.",
                    details={"thread": writer.thread_name},
                )
            )
        stuck_readers = _join_reader_threads(self.stderr_threads, deadline=cleanup_deadline)
        for thread_name in stuck_readers:
            self.stop_event.set()
            cleanup_failures.append(
                ProcessError(
                    TaskErrorCode.PROCESS_FAILED,
                    "Stage worker stderr reader did not exit before the cleanup deadline.",
                    details={"thread": thread_name},
                )
            )
        if not cleanup_failures and not stuck_readers and writers_joined:
            _close_worker_pipes(self.handles)
            return ()
        return tuple(cleanup_failures)


@contextmanager
def stage_worker_session(
    configs: list[StageWorkerConfig],
    *,
    progress_callbacks: Sequence[StageProgressCallback | None],
    error_queue: queue.Queue[BaseException],
    stop_event: threading.Event,
    worker_log_sink: WorkerLogSink,
) -> Iterator[StageWorkerGroup]:
    with tempfile.TemporaryDirectory(prefix="vp-stage-workers-") as config_dir:
        group = StageWorkerGroup.start(
            configs,
            config_dir=Path(config_dir),
            progress_callbacks=progress_callbacks,
            error_queue=error_queue,
            stop_event=stop_event,
            worker_log_sink=worker_log_sink,
        )

        try:
            yield group
        except BaseException:
            group.close()
            raise
        else:
            try:
                group.finish_successfully()
            except BaseException:
                group.close()
                raise


__all__ = [
    "stage_worker_session",
]
