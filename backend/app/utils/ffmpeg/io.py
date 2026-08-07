"""Raw video pipe handling: command builders and reader/writer classes."""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any, Callable

import numpy as np

from app.generated.protocol_constants import TERMINATION_REAP_TIMEOUT_MS
from app.utils.late_cleanup import late_cleanup_coordinator
from app.utils.subprocess_utils import hidden_subprocess_kwargs

from ._constants import FFMPEG_PROGRESS_KEYS
from ._progress import _parse_progress_snapshot


class _FFmpegPipeBase:
    """Common lifecycle handling for FFmpeg pipe processes."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._process = process
        self._progress_callback = progress_callback
        self._stderr_lines: list[str] = []
        self._latest_progress: dict[str, Any] = {}
        self._stderr_error: BaseException | None = None
        self._stderr_thread = threading.Thread(target=self._collect_stderr, daemon=False)
        try:
            self._stderr_thread.start()
        except BaseException as start_error:
            cleanup_complete = False
            try:
                cleanup_complete = self.retry_cleanup(
                    deadline=time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000,
                )
            except BaseException as cleanup_error:  # pragma: no cover - constructor rollback boundary
                start_error.add_note(f"Immediate FFmpeg cleanup failed: {cleanup_error}")
            if not cleanup_complete:
                try:
                    late_cleanup_coordinator.submit(self)
                except BaseException as submit_error:  # pragma: no cover - last-resort ownership boundary
                    start_error.add_note(f"Late FFmpeg cleanup submission failed: {submit_error}")
            raise

    def _collect_stderr(self) -> None:
        if self._process.stderr is None:
            return
        progress_state: dict[str, str] = {}
        try:
            for raw_line in iter(self._process.stderr.readline, b""):
                text = raw_line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue

                if "=" in text:
                    key, value = text.split("=", 1)
                    if key in FFMPEG_PROGRESS_KEYS:
                        progress_state[key] = value
                        if key == "progress":
                            try:
                                self._update_progress(progress_state)
                            except BaseException as exc:  # pragma: no cover - callback boundary
                                self._record_stderr_error(exc)
                            progress_state = {}
                        continue

                self._stderr_lines.append(text)
        except BaseException as exc:  # pragma: no cover - process pipe boundary
            self._record_stderr_error(exc)

    def _record_stderr_error(self, error: BaseException) -> None:
        if self._stderr_error is None:
            self._stderr_error = error

    def _update_progress(self, snapshot: dict[str, str]) -> None:
        parsed = _parse_progress_snapshot(snapshot)
        self._latest_progress = parsed
        if self._progress_callback is None:
            return
        self._progress_callback(parsed)

    def _wait_for_process(self, *, deadline: float | None = None) -> None:
        if deadline is None:
            return_code = self._process.wait()
        else:
            remaining = max(deadline - time.monotonic(), 0.0)
            cleanup_reserve = min(1.0, remaining / 2)
            try:
                return_code = self._process.wait(timeout=max(remaining - cleanup_reserve, 0.0))
            except subprocess.TimeoutExpired as exc:
                reaped = self.terminate_and_reap(deadline=deadline)
                status = "reaped" if reaped else "cleanup incomplete"
                raise RuntimeError(f"FFmpeg pipe command missed its cleanup deadline ({status}).") from exc
        self._stderr_thread.join(timeout=None if deadline is None else max(deadline - time.monotonic(), 0.0))
        if self._stderr_thread.is_alive():
            raise RuntimeError("FFmpeg stderr reader did not exit before the cleanup deadline.")
        if self._stderr_error is not None:
            raise RuntimeError("FFmpeg stderr collection failed.") from self._stderr_error
        if return_code != 0:
            message = "\n".join(self._stderr_lines[-20:]) or f"FFmpeg exited with code {return_code}"
            raise RuntimeError(f"FFmpeg pipe command failed ({return_code}): {message}")

    def terminate_and_reap(self, *, deadline: float) -> bool:
        """Terminate and reap the child under one caller-owned monotonic deadline."""
        if self._process.poll() is None:
            try:
                self._process.terminate()
            except OSError:
                if self._process.poll() is None:
                    return False
            remaining = max(deadline - time.monotonic(), 0.0)
            terminate_wait = remaining / 2
            try:
                self._process.wait(timeout=terminate_wait)
            except subprocess.TimeoutExpired:
                try:
                    self._process.kill()
                except OSError:
                    if self._process.poll() is None:
                        return False
                try:
                    self._process.wait(timeout=max(deadline - time.monotonic(), 0.0))
                except subprocess.TimeoutExpired:
                    return False
        if self._stderr_thread.ident is not None:
            self._stderr_thread.join(timeout=max(deadline - time.monotonic(), 0.0))
        return self._process.poll() is not None and not self._stderr_thread.is_alive()

    def retry_cleanup(self, *, deadline: float) -> bool:
        return self.terminate_and_reap(deadline=deadline)


class _RawVideoReader(_FFmpegPipeBase):
    """Read `rgb24` rawvideo frames from an FFmpeg stdout pipe."""

    def __init__(self, *, process: subprocess.Popen[bytes], width: int, height: int):
        super().__init__(process)
        self._width = width
        self._height = height
        self._frame_bytes = width * height * 3

    def read_frame(self) -> np.ndarray | None:
        if self._process.stdout is None:
            raise RuntimeError("FFmpeg stdout pipe is not available.")

        chunks: list[bytes] = []
        remaining = self._frame_bytes
        while remaining > 0:
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                if not chunks:
                    return None
                break
            chunks.append(chunk)
            remaining -= len(chunk)

        if remaining != 0:
            self._wait_for_process(deadline=time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000)
            raise RuntimeError("FFmpeg rawvideo decoder produced a partial frame.")

        frame = np.frombuffer(b"".join(chunks), dtype=np.uint8)
        return frame.reshape((self._height, self._width, 3))

    def close(self) -> None:
        if self._process.stdout is not None:
            self._process.stdout.close()
        self._wait_for_process(deadline=time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000)


class _RawVideoWriter(_FFmpegPipeBase):
    """Write `rgb24` rawvideo frames into an FFmpeg stdin pipe."""

    def __init__(
        self,
        *,
        process: subprocess.Popen[bytes],
        width: int,
        height: int,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        super().__init__(process, progress_callback=progress_callback)
        self._width = width
        self._height = height

    def write_frame(self, frame: np.ndarray) -> None:
        if self._process.stdin is None:
            raise RuntimeError("FFmpeg stdin pipe is not available.")
        if frame.shape != (self._height, self._width, 3):
            raise ValueError(f"Frame shape mismatch: expected {(self._height, self._width, 3)}, got {frame.shape}")
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        self._process.stdin.write(np.ascontiguousarray(frame).tobytes())

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        self._wait_for_process(deadline=time.monotonic() + TERMINATION_REAP_TIMEOUT_MS / 1000)

    @property
    def output_frame_count(self) -> int:
        return int(self._latest_progress.get("frame") or 0)


def _build_rawvideo_decode_command(
    ffmpeg_path: str,
    *,
    width: int,
    height: int,
    decode_input_args: list[str],
    start_frame: int = 0,
    frame_count: int | None = None,
) -> list[str]:
    """Build FFmpeg command for rawvideo decoding."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive for rawvideo decode.")
    cmd = [ffmpeg_path, "-hide_banner", "-loglevel", "error"]
    cmd.extend(decode_input_args)
    if start_frame > 0:
        cmd.extend(["-vf", f"select=gte(n\\,{start_frame})"])
    cmd.extend(["-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "-vsync", "0"])
    if frame_count is not None and frame_count > 0:
        cmd.extend(["-frames:v", str(int(frame_count))])
    cmd.append("-")
    return cmd


def _build_rawvideo_encode_command(
    ffmpeg_path: str,
    *,
    width: int,
    height: int,
    fps: float,
    output_fps: float | None = None,
    encode_output_args: list[str],
) -> list[str]:
    """Build FFmpeg command for rawvideo encoding."""
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-progress",
        "pipe:2",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "-",
    ]
    if output_fps is not None and abs(output_fps - fps) > 0.01:
        cmd.extend(["-r", str(output_fps)])
    cmd.extend(encode_output_args)
    return cmd


def open_rawvideo_decoder(
    ffmpeg_path: str,
    *,
    width: int,
    height: int,
    decode_input_args: list[str],
    start_frame: int = 0,
    frame_count: int | None = None,
) -> _RawVideoReader:
    """Open a rawvideo decoder pipe."""
    cmd = _build_rawvideo_decode_command(
        ffmpeg_path,
        width=width,
        height=height,
        decode_input_args=decode_input_args,
        start_frame=start_frame,
        frame_count=frame_count,
    )
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        **hidden_subprocess_kwargs(),
    )
    return _RawVideoReader(process=process, width=width, height=height)


def open_rawvideo_encoder(
    ffmpeg_path: str,
    *,
    width: int,
    height: int,
    fps: float,
    output_fps: float | None = None,
    encode_output_args: list[str],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> _RawVideoWriter:
    """Open a rawvideo encoder pipe."""
    cmd = _build_rawvideo_encode_command(
        ffmpeg_path,
        width=width,
        height=height,
        fps=fps,
        output_fps=output_fps,
        encode_output_args=encode_output_args,
    )
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        bufsize=0,
        **hidden_subprocess_kwargs(),
    )
    return _RawVideoWriter(
        process=process,
        width=width,
        height=height,
        progress_callback=progress_callback,
    )
