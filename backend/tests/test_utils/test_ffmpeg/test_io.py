"""Rawvideo command and bounded process lifecycle rules."""

from __future__ import annotations

import io
import subprocess
import time

import pytest

from app.utils.ffmpeg.io import (
    RawVideoReader,
    _build_rawvideo_decode_command,
    _build_rawvideo_encode_command,
    open_rawvideo_decoder,
    open_rawvideo_encoder,
)


def test_build_rawvideo_commands_include_pipe_and_geometry() -> None:
    decode_cmd = _build_rawvideo_decode_command(
        "ffmpeg",
        width=1920,
        height=1080,
        decode_input_args=["-i", "input.mp4"],
        start_frame=25,
        frame_count=1000,
    )
    encode_cmd = _build_rawvideo_encode_command(
        "ffmpeg",
        width=1920,
        height=1080,
        fps=48.0,
        output_fps=60.0,
        encode_output_args=["-c:v", "libx264", "output.mp4", "-y"],
    )

    assert decode_cmd[:3] == ["ffmpeg", "-hide_banner", "-loglevel"]
    assert "-vf" in decode_cmd
    assert "select=gte(n\\,25)" in decode_cmd
    assert "-frames:v" in decode_cmd
    assert "1000" in decode_cmd
    assert decode_cmd[-1] == "-"

    assert encode_cmd[:3] == ["ffmpeg", "-hide_banner", "-loglevel"]
    assert "-progress" in encode_cmd
    assert "pipe:2" in encode_cmd
    assert "-s" in encode_cmd
    assert "1920x1080" in encode_cmd
    assert "-framerate" in encode_cmd
    assert "48.0" in encode_cmd
    assert "-r" in encode_cmd
    assert "60.0" in encode_cmd
    assert "output.mp4" in encode_cmd


def test_rawvideo_pipe_terminate_wait_kill_reap_uses_one_deadline() -> None:
    lifecycle: list[str] = []
    killed = False

    class Process:
        stdout = io.BytesIO()
        stderr = io.BytesIO()

        def poll(self):
            return -9 if killed else None

        def terminate(self) -> None:
            lifecycle.append("terminate")

        def kill(self) -> None:
            nonlocal killed
            lifecycle.append("kill")
            killed = True

        def wait(self, timeout=None) -> int:
            lifecycle.append("reap")
            if not killed:
                raise subprocess.TimeoutExpired("ffmpeg", timeout)
            return -9

    reader = RawVideoReader(process=Process(), width=1, height=1)  # type: ignore[arg-type]

    assert reader.terminate_and_reap(deadline=time.monotonic() + 1) is True
    assert lifecycle == ["terminate", "reap", "kill", "reap"]


def test_rawvideo_factories_use_unbuffered_pipes_to_avoid_cross_thread_buffer_locks(monkeypatch) -> None:
    popen_calls: list[dict] = []

    class Process:
        stdin = io.BytesIO()
        stdout = io.BytesIO()
        stderr = io.BytesIO()

        def poll(self) -> int:
            return 0

        def wait(self, **_kwargs) -> int:
            return 0

    def popen(_command, **kwargs):
        popen_calls.append(kwargs)
        return Process()

    monkeypatch.setattr("app.utils.ffmpeg.io.subprocess.Popen", popen)

    open_rawvideo_decoder("ffmpeg", width=1, height=1, decode_input_args=["-i", "in.mp4"])
    open_rawvideo_encoder(
        "ffmpeg",
        width=1,
        height=1,
        fps=24.0,
        encode_output_args=["out.mp4"],
    )

    assert [call["bufsize"] for call in popen_calls] == [0, 0]


def test_rawvideo_factories_reap_process_when_stderr_thread_fails_to_start(monkeypatch) -> None:
    lifecycle: list[str] = []

    class Process:
        stdin = io.BytesIO()
        stdout = io.BytesIO()
        stderr = io.BytesIO()
        exited = False

        def poll(self):
            return 0 if self.exited else None

        def terminate(self) -> None:
            lifecycle.append("terminate")

        def kill(self) -> None:
            lifecycle.append("kill")
            self.exited = True

        def wait(self, **_kwargs) -> int:
            lifecycle.append("wait")
            self.exited = True
            return 0

    monkeypatch.setattr("app.utils.ffmpeg.io.subprocess.Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(
        "app.utils.ffmpeg.io.threading.Thread.start", lambda _thread: (_ for _ in ()).throw(OSError("start failed"))
    )

    for factory in (
        lambda: open_rawvideo_decoder("ffmpeg", width=1, height=1, decode_input_args=["-i", "in.mp4"]),
        lambda: open_rawvideo_encoder(
            "ffmpeg",
            width=1,
            height=1,
            fps=24.0,
            encode_output_args=["out.mp4"],
        ),
    ):
        with pytest.raises(OSError, match="start failed"):
            factory()

    assert lifecycle == ["terminate", "wait", "terminate", "wait"]


def test_rawvideo_writer_surfaces_progress_callback_failure_after_draining_stderr() -> None:
    class Process:
        stdin = io.BytesIO()
        stderr = io.BytesIO(b"frame=1\nprogress=continue\nframe=2\nprogress=end\n")

        def poll(self) -> int:
            return 0

        def wait(self, **_kwargs) -> int:
            return 0

    from app.utils.ffmpeg.io import RawVideoWriter

    writer = RawVideoWriter(
        process=Process(),  # type: ignore[arg-type]
        width=1,
        height=1,
        progress_callback=lambda _progress: (_ for _ in ()).throw(RuntimeError("callback failed")),
    )

    with pytest.raises(RuntimeError, match="stderr collection failed") as exc_info:
        writer.close()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert writer.output_frame_count == 2


def test_rawvideo_writer_surfaces_stderr_pipe_read_failure() -> None:
    class FailingStderr:
        def readline(self) -> bytes:
            raise OSError("stderr read failed")

    class Process:
        stdin = io.BytesIO()
        stderr = FailingStderr()

        def poll(self) -> int:
            return 0

        def wait(self, **_kwargs) -> int:
            return 0

    from app.utils.ffmpeg.io import RawVideoWriter

    writer = RawVideoWriter(process=Process(), width=1, height=1)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="stderr collection failed") as exc_info:
        writer.close()

    assert isinstance(exc_info.value.__cause__, OSError)


def test_stderr_thread_start_preserves_original_error_when_cleanup_throws_and_retains_owner(monkeypatch) -> None:
    submitted: list[object] = []

    class Process:
        stdout = io.BytesIO()
        stderr = io.BytesIO()

    monkeypatch.setattr(
        "app.utils.ffmpeg.io.threading.Thread.start",
        lambda _thread: (_ for _ in ()).throw(OSError("thread start failed")),
    )
    monkeypatch.setattr(
        "app.utils.ffmpeg.io._FFmpegPipeBase.retry_cleanup",
        lambda _self, *, deadline: (_ for _ in ()).throw(RuntimeError(f"cleanup failed at {deadline}")),
    )
    monkeypatch.setattr("app.utils.ffmpeg.io.late_cleanup_coordinator.submit", submitted.append)

    with pytest.raises(OSError, match="thread start failed") as exc_info:
        RawVideoReader(process=Process(), width=1, height=1)  # type: ignore[arg-type]

    assert submitted
    assert any("cleanup failed" in note for note in exc_info.value.__notes__)


def test_partial_rawvideo_frame_wait_uses_finite_cleanup_deadline() -> None:
    process = type("Process", (), {"stdout": io.BytesIO(b"x"), "stderr": io.BytesIO()})()
    reader = RawVideoReader(process=process, width=1, height=1)  # type: ignore[arg-type]
    deadlines: list[float] = []
    reader._wait_for_process = lambda *, deadline: deadlines.append(deadline)  # type: ignore[method-assign]

    try:
        reader.read_frame()
    except RuntimeError as exc:
        assert "partial frame" in str(exc)
    else:
        raise AssertionError("partial rawvideo frame should fail")

    assert len(deadlines) == 1
    assert time.monotonic() < deadlines[0] < time.monotonic() + 6
