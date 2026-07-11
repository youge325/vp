"""Raw video pipe handling: command builders and reader/writer classes."""

from __future__ import annotations

import subprocess
import threading
from typing import Any, Callable

import numpy as np

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
        self._stderr_thread = threading.Thread(target=self._collect_stderr, daemon=True)
        self._stderr_thread.start()

    def _collect_stderr(self) -> None:
        if self._process.stderr is None:
            return
        progress_state: dict[str, str] = {}
        for raw_line in iter(self._process.stderr.readline, b""):
            text = raw_line.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            if "=" in text:
                key, value = text.split("=", 1)
                if key in FFMPEG_PROGRESS_KEYS:
                    progress_state[key] = value
                    if key == "progress":
                        self._update_progress(progress_state)
                        progress_state = {}
                    continue

            self._stderr_lines.append(text)

    def _update_progress(self, snapshot: dict[str, str]) -> None:
        parsed = _parse_progress_snapshot(snapshot)
        self._latest_progress = parsed
        if self._progress_callback is None:
            return
        self._progress_callback(parsed)

    def _wait_for_process(self) -> None:
        return_code = self._process.wait()
        self._stderr_thread.join(timeout=1)
        if return_code != 0:
            message = "\n".join(self._stderr_lines[-20:]) or f"FFmpeg exited with code {return_code}"
            raise RuntimeError(f"FFmpeg pipe command failed ({return_code}): {message}")


class RawVideoReader(_FFmpegPipeBase):
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
            self._wait_for_process()
            raise RuntimeError("FFmpeg rawvideo decoder produced a partial frame.")

        frame = np.frombuffer(b"".join(chunks), dtype=np.uint8)
        return frame.reshape((self._height, self._width, 3))

    def close(self) -> None:
        if self._process.stdout is not None:
            self._process.stdout.close()
        self._wait_for_process()


class RawVideoWriter(_FFmpegPipeBase):
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
        self._wait_for_process()

    @property
    def output_frame_count(self) -> int:
        return int(self._latest_progress.get("frame") or 0)


def _build_rawvideo_decode_command(
    ffmpeg_path: str,
    input_path: str,
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
    output_path: str,
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
    input_path: str,
    width: int,
    height: int,
    decode_input_args: list[str],
    start_frame: int = 0,
    frame_count: int | None = None,
) -> RawVideoReader:
    """Open a rawvideo decoder pipe."""
    cmd = _build_rawvideo_decode_command(
        ffmpeg_path,
        input_path,
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
        **hidden_subprocess_kwargs(),
    )
    return RawVideoReader(process=process, width=width, height=height)


def open_rawvideo_encoder(
    ffmpeg_path: str,
    *,
    output_path: str,
    width: int,
    height: int,
    fps: float,
    output_fps: float | None = None,
    encode_output_args: list[str],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> RawVideoWriter:
    """Open a rawvideo encoder pipe."""
    cmd = _build_rawvideo_encode_command(
        ffmpeg_path,
        output_path,
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
        **hidden_subprocess_kwargs(),
    )
    return RawVideoWriter(
        process=process,
        width=width,
        height=height,
        progress_callback=progress_callback,
    )
