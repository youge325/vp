"""FFmpeg command wrapper and capability probing."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any, Callable

import numpy as np

from app.utils.logger import get_logger
from app.utils.subprocess_utils import hidden_subprocess_kwargs

logger = get_logger(__name__)


ENCODER_CANDIDATES = (
    {"name": "libx264", "label": "CPU H.264", "family": "cpu", "codec": "h264"},
    {"name": "libx265", "label": "CPU H.265", "family": "cpu", "codec": "hevc"},
    {"name": "libaom-av1", "label": "CPU AV1", "family": "cpu", "codec": "av1"},
    {"name": "libsvtav1", "label": "CPU SVT-AV1", "family": "cpu", "codec": "av1"},
    {"name": "h264_nvenc", "label": "NVENC H.264", "family": "nvidia", "codec": "h264"},
    {"name": "hevc_nvenc", "label": "NVENC H.265", "family": "nvidia", "codec": "hevc"},
    {"name": "av1_nvenc", "label": "NVENC AV1", "family": "nvidia", "codec": "av1"},
    {"name": "h264_qsv", "label": "QSV H.264", "family": "intel", "codec": "h264"},
    {"name": "hevc_qsv", "label": "QSV H.265", "family": "intel", "codec": "hevc"},
    {"name": "av1_qsv", "label": "QSV AV1", "family": "intel", "codec": "av1"},
)

DECODER_CANDIDATES = (
    {"name": "h264_cuvid", "label": "NVDEC H.264", "family": "nvidia", "codec": "h264"},
    {"name": "hevc_cuvid", "label": "NVDEC H.265", "family": "nvidia", "codec": "hevc"},
    {"name": "av1_cuvid", "label": "NVDEC AV1", "family": "nvidia", "codec": "av1"},
    {"name": "h264_qsv", "label": "QSV H.264", "family": "intel", "codec": "h264"},
    {"name": "hevc_qsv", "label": "QSV H.265", "family": "intel", "codec": "hevc"},
    {"name": "av1_qsv", "label": "QSV AV1", "family": "intel", "codec": "av1"},
)

OPTION_LINE_RE = re.compile(
    r"^\s{2}-(?P<name>[\w\-]+)\s+<(?P<kind>[^>]+)>\s+.*?"
    r"(?:\(from (?P<min>[^ ]+) to (?P<max>[^)]+)\))?"
    r"(?: \(default (?P<default>[^)]+)\))?$"
)
CHOICE_LINE_RE = re.compile(r"^\s{5,}(?P<value>\S+)\s+\S+\s+")
CODEC_LIST_RE = re.compile(r"^\s*[A-Z\.]{6}\s+(?P<name>[\w\-]+)\s+")
FFMPEG_PROGRESS_KEYS = {
    "bitrate",
    "drop_frames",
    "dup_frames",
    "fps",
    "frame",
    "out_time",
    "out_time_ms",
    "out_time_us",
    "progress",
    "speed",
    "total_size",
}


def _parse_progress_float(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    text = raw_value.strip()
    if not text or text.upper() == "N/A":
        return None
    if text.endswith("x"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def _parse_progress_int(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    text = raw_value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_progress_out_time_seconds(snapshot: dict[str, str]) -> float | None:
    for key in ("out_time_us", "out_time_ms"):
        value = _parse_progress_int(snapshot.get(key))
        if value is None:
            continue
        scale = 1_000_000 if key == "out_time_us" else 1_000
        return value / scale

    raw_value = snapshot.get("out_time")
    if not raw_value:
        return None

    try:
        hours, minutes, seconds = raw_value.strip().split(":")
        return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    except ValueError:
        return None


def _parse_progress_snapshot(snapshot: dict[str, str]) -> dict[str, Any]:
    return {
        "frame": _parse_progress_int(snapshot.get("frame")) or 0,
        "fps": _parse_progress_float(snapshot.get("fps")),
        "speed": _parse_progress_float(snapshot.get("speed")),
        "out_time_seconds": _parse_progress_out_time_seconds(snapshot),
        "progress": snapshot.get("progress", ""),
    }


def _coerce_number(value: str | None) -> int | float | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"int_max", "auto", "unknown", "-inf", "inf"}:
        return None
    try:
        if "." in lowered:
            return float(lowered)
        return int(lowered)
    except ValueError:
        return None


def _coerce_default_value(kind: str, raw: str | None) -> Any:
    if raw is None:
        return None
    text = raw.strip()
    if kind == "boolean":
        return text.lower() in {"1", "true", "yes", "on", "auto"}
    if kind == "number":
        return _coerce_number(text)
    return text


def _format_bitrate(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return "8M"
    if text.lower().endswith(("k", "m", "g")):
        return text.upper()
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return f"{int(numeric)}M"
    return f"{numeric}M"


class FFmpegWrapper:
    """Wrap FFmpeg/FFprobe calls and normalize runtime capabilities."""

    def __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None):
        self._ffmpeg_path_explicit = ffmpeg_path is not None
        self._ffprobe_path_explicit = ffprobe_path is not None
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.ffprobe_path = ffprobe_path or "ffprobe"
        self._auto_detect_paths()
        # Probe caches keyed by (abspath, mtime_ns); invalidates on file mutation.
        self._video_info_cache: dict[tuple[str, int], dict[str, Any]] = {}
        self._frame_count_cache: dict[tuple[str, int], int] = {}

    def _probe_cache_key(self, input_path: str) -> tuple[str, int] | None:
        try:
            stat = os.stat(input_path)
        except OSError:
            return None
        return (os.path.abspath(input_path), stat.st_mtime_ns)

    def get_video_info(self, input_path: str) -> dict[str, Any]:
        cache_key = self._probe_cache_key(input_path)
        if cache_key is not None and cache_key in self._video_info_cache:
            return self._video_info_cache[cache_key]

        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]
        result = self._run_command(cmd)
        try:
            info = json.loads(result.stdout)
        except json.JSONDecodeError:
            info = {}
        if cache_key is not None:
            self._video_info_cache[cache_key] = info
        return info

    def get_fps(self, input_path: str) -> float:
        info = self.get_video_info(input_path)
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                frame_rate = str(stream.get("r_frame_rate", "30/1"))
                numerator, _, denominator = frame_rate.partition("/")
                try:
                    numerator_value = int(numerator)
                    denominator_value = int(denominator or "1")
                except ValueError:
                    return 30.0
                if denominator_value == 0:
                    return 30.0
                return round(numerator_value / denominator_value, 3)
        return 30.0

    def get_frame_count(self, input_path: str) -> int:
        cache_key = self._probe_cache_key(input_path)
        if cache_key is not None and cache_key in self._frame_count_cache:
            return self._frame_count_cache[cache_key]

        # 优先使用容器/流元数据中的 nb_frames（O(1)），只有缺失/异常时才退化为
        # -count_frames 扫描。后者在 4K HEVC 等大视频上需要几分钟软解全片。
        frame_count = self._frame_count_from_metadata(input_path)

        if frame_count <= 0:
            cmd = [
                self.ffprobe_path,
                "-v",
                "quiet",
                "-count_frames",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=nb_read_frames",
                "-print_format",
                "json",
                input_path,
            ]
            result = self._run_command(cmd)
            try:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])
                if streams:
                    frame_count = int(streams[0].get("nb_read_frames", 0))
            except (json.JSONDecodeError, ValueError, IndexError):
                pass

        if frame_count <= 0:
            duration = self.get_duration(input_path)
            fps = self.get_fps(input_path)
            frame_count = int(duration * fps) if duration > 0 else 0

        if cache_key is not None and frame_count > 0:
            self._frame_count_cache[cache_key] = frame_count
        return frame_count

    def _frame_count_from_metadata(self, input_path: str) -> int:
        """从容器/流元数据中解析帧数（不进行解码扫描）。

        ffprobe 默认输出的 stream.nb_frames 由容器写入；TS/MP4 等格式通常都有，
        损坏或恶意写入的文件会导致 0/缺失。返回 0 表示元数据不可信。
        """
        info = self.get_video_info(input_path)
        for stream in info.get("streams", []):
            if stream.get("codec_type") != "video":
                continue
            raw = stream.get("nb_frames")
            if raw is None:
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return 0

    def get_duration(self, input_path: str) -> float:
        info = self.get_video_info(input_path)
        return float(info.get("format", {}).get("duration", 0))

    def has_audio(self, input_path: str) -> bool:
        info = self.get_video_info(input_path)
        return any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))

    def get_primary_video_codec(self, input_path: str) -> str:
        info = self.get_video_info(input_path)
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                return str(stream.get("codec_name") or "")
        return ""

    def build_rawvideo_decode_command(
        self,
        input_path: str,
        *,
        width: int,
        height: int,
        decode_config: dict[str, Any] | None = None,
        start_frame: int = 0,
    ) -> list[str]:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive for rawvideo decode.")
        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error"]
        cmd.extend(self.build_decode_input_args(input_path, decode_config))
        if start_frame > 0:
            cmd.extend(["-vf", f"select=gte(n\\,{start_frame})"])
        cmd.extend(["-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "-vsync", "0", "-"])
        return cmd

    def build_rawvideo_encode_command(
        self,
        output_path: str,
        *,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        encode_config: dict[str, Any] | None = None,
    ) -> list[str]:
        cmd = [
            self.ffmpeg_path,
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
        cmd.extend(self.build_encode_output_args(output_path, encode_config))
        return cmd

    def open_rawvideo_decoder(
        self,
        *,
        input_path: str,
        width: int,
        height: int,
        decode_config: dict[str, Any] | None = None,
        start_frame: int = 0,
    ) -> "RawVideoReader":
        cmd = self.build_rawvideo_decode_command(
            input_path,
            width=width,
            height=height,
            decode_config=decode_config,
            start_frame=start_frame,
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
        self,
        *,
        output_path: str,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        encode_config: dict[str, Any] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> "RawVideoWriter":
        cmd = self.build_rawvideo_encode_command(
            output_path,
            width=width,
            height=height,
            fps=fps,
            output_fps=output_fps,
            encode_config=encode_config,
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

    def extract_audio(self, input_path: str, output_path: str) -> str | None:
        cmd = [self.ffmpeg_path, "-i", input_path, "-vn", "-acodec", "copy", output_path, "-y"]
        try:
            self._run_command(cmd)
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.warning("Audio extraction failed: %s", exc)
            return None
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        return None

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        cmd = [
            self.ffmpeg_path,
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            output_path,
            "-y",
        ]
        self._run_command(cmd)
        return output_path

    def concat_videos(self, segment_paths: list[str], output_path: str) -> str:
        if not segment_paths:
            raise ValueError("segment_paths must not be empty")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        list_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                suffix=".concat.txt",
                dir=os.path.dirname(output_path) or ".",
                delete=False,
            ) as handle:
                list_file_path = handle.name
                for path in segment_paths:
                    normalized = path.replace("\\", "/").replace("'", "'\\''")
                    handle.write(f"file '{normalized}'\n")

            cmd = [
                self.ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file_path,
                "-c",
                "copy",
                output_path,
                "-y",
            ]
            self._run_command(cmd)
            return output_path
        finally:
            if list_file_path and os.path.isfile(list_file_path):
                os.remove(list_file_path)

    def transcode_video(
        self,
        *,
        input_path: str,
        output_path: str,
        decode_config: dict[str, Any] | None = None,
        encode_config: dict[str, Any] | None = None,
        output_fps: float | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        encode_config = encode_config or {}
        keep_audio = bool(encode_config.get("keepAudio", True))

        cmd = [self.ffmpeg_path, "-hide_banner", "-loglevel", "error"]
        if progress_callback is not None:
            cmd.extend(["-nostats", "-progress", "pipe:2"])
        cmd.extend(self.build_decode_input_args(input_path, decode_config))
        cmd.extend(["-map", "0:v:0"])
        if keep_audio:
            cmd.extend(["-map", "0:a?", "-c:a", "aac"])
        else:
            cmd.append("-an")
        if output_fps is not None:
            cmd.extend(["-r", str(output_fps)])
        cmd.extend(self.build_encode_output_args(output_path, encode_config))
        if progress_callback is None:
            self._run_command(cmd)
            return output_path

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            **hidden_subprocess_kwargs(),
        )
        monitor = _FFmpegPipeBase(process, progress_callback=progress_callback)
        monitor._wait_for_process()
        return output_path

    def convert_format(
        self,
        input_path: str,
        output_path: str,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
        audio_codec: str = "aac",
    ) -> str:
        cmd = [
            self.ffmpeg_path,
            "-i",
            input_path,
            "-c:v",
            codec,
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-c:a",
            audio_codec,
            output_path,
            "-y",
        ]
        self._run_command(cmd)
        return output_path

    def list_codec_names(self, mode: str) -> list[str]:
        if mode not in {"encoders", "decoders"}:
            raise ValueError(f"Unsupported codec list mode: {mode}")
        cmd = [self.ffmpeg_path, "-hide_banner", f"-{mode}"]
        result = self._run_command(cmd, timeout=30)
        names: list[str] = []
        for line in result.stdout.splitlines():
            match = CODEC_LIST_RE.match(line)
            if match:
                names.append(match.group("name"))
        return names

    def list_hwaccels(self) -> list[str]:
        result = self._run_command([self.ffmpeg_path, "-hide_banner", "-hwaccels"], timeout=30)
        hwaccels: list[str] = []
        started = False
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Hardware acceleration methods"):
                started = True
                continue
            if started:
                hwaccels.append(stripped)
        return hwaccels

    def describe_codec(self, mode: str, name: str) -> str:
        if mode not in {"encoder", "decoder"}:
            raise ValueError(f"Unsupported codec help mode: {mode}")
        result = self._run_command([self.ffmpeg_path, "-hide_banner", "-h", f"{mode}={name}"], timeout=30)
        return result.stdout

    def parse_codec_profile(
        self,
        mode: str,
        metadata: dict[str, Any],
        help_text: str,
    ) -> dict[str, Any]:
        pixel_formats = self._parse_supported_values(help_text, "Supported pixel formats:")
        hardware_devices = self._parse_supported_values(help_text, "Supported hardware devices:")
        options = self.parse_avoptions(help_text)
        if pixel_formats:
            options.insert(
                0,
                {
                    "name": "pix_fmt",
                    "label": "Pixel Format",
                    "type": "choice",
                    "defaultValue": pixel_formats[0],
                    "choices": [{"label": value, "value": value} for value in pixel_formats],
                    "min": None,
                    "max": None,
                },
            )
        return {
            "name": metadata["name"],
            "label": metadata["label"],
            "family": metadata["family"],
            "codec": metadata["codec"],
            "available": True,
            "pixelFormats": pixel_formats,
            "hardwareDevices": hardware_devices,
            "options": options,
        }

    def parse_avoptions(self, help_text: str) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line in help_text.splitlines():
            match = OPTION_LINE_RE.match(line.rstrip())
            if match:
                raw_kind = match.group("kind").strip()
                option_type = "string"
                if raw_kind == "boolean":
                    option_type = "boolean"
                elif raw_kind in {"int", "float", "double"}:
                    option_type = "number"
                option = {
                    "name": match.group("name"),
                    "label": match.group("name").replace("_", " "),
                    "type": option_type,
                    "defaultValue": _coerce_default_value(option_type, match.group("default")),
                    "choices": [],
                    "min": _coerce_number(match.group("min")),
                    "max": _coerce_number(match.group("max")),
                }
                options.append(option)
                current = option
                continue

            choice_match = CHOICE_LINE_RE.match(line.rstrip())
            if choice_match and current is not None:
                choice_value = choice_match.group("value")
                current["choices"].append({"label": choice_value, "value": choice_value})

        normalized: list[dict[str, Any]] = []
        for option in options:
            normalized_option = dict(option)
            if normalized_option["choices"]:
                normalized_option["type"] = "choice"
            normalized.append(normalized_option)
        return normalized

    def discover_capabilities(self, gpu_adapters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        adapters = gpu_adapters or []
        available_vendors = {adapter.get("vendor") for adapter in adapters if adapter.get("device_type") != "virtual"}
        encoder_names = set(self.list_codec_names("encoders"))
        decoder_names = set(self.list_codec_names("decoders"))
        hwaccels = self.list_hwaccels()

        encoder_profiles: list[dict[str, Any]] = []
        for candidate in ENCODER_CANDIDATES:
            if candidate["name"] not in encoder_names:
                continue
            if candidate["family"] != "cpu" and candidate["family"] not in available_vendors:
                continue
            encoder_profiles.append(
                self.parse_codec_profile("encoder", candidate, self.describe_codec("encoder", candidate["name"]))
            )

        decoder_profiles: list[dict[str, Any]] = [
            {
                "name": "software",
                "label": "Software Decode",
                "family": "software",
                "codec": "any",
                "available": True,
                "pixelFormats": [],
                "hardwareDevices": [],
                "options": [],
            }
        ]
        for candidate in DECODER_CANDIDATES:
            if candidate["name"] not in decoder_names:
                continue
            if candidate["family"] not in available_vendors:
                continue
            decoder_profiles.append(
                self.parse_codec_profile("decoder", candidate, self.describe_codec("decoder", candidate["name"]))
            )

        return {
            "hwaccels": hwaccels,
            "encoderProfiles": encoder_profiles,
            "decoderProfiles": decoder_profiles,
        }

    def build_decode_input_args(self, input_path: str, decode_config: dict[str, Any] | None = None) -> list[str]:
        decode_config = decode_config or {}
        mode = decode_config.get("mode", "software")
        args: list[str] = []

        if mode == "hardware":
            hwaccel = str(decode_config.get("hwaccel") or "").strip()
            if hwaccel:
                args.extend(["-hwaccel", hwaccel])
            hwaccel_device = str(decode_config.get("hwaccelDevice") or "").strip()
            if hwaccel_device:
                args.extend(["-hwaccel_device", hwaccel_device])

        decoder = str(decode_config.get("decoder") or "").strip()
        if decoder and decoder != "software":
            args.extend(["-c:v", decoder])

        args.extend(self._build_option_args(decode_config.get("options", {})))
        args.extend(["-i", input_path])
        return args

    def build_encode_video_args(self, encode_config: dict[str, Any] | None = None) -> list[str]:
        encode_config = encode_config or {}
        codec = str(encode_config.get("codec") or "libx264")
        options = dict(encode_config.get("options", {}))
        if "pix_fmt" not in options:
            default_pix_fmt = self._default_pix_fmt(codec)
            if default_pix_fmt:
                options["pix_fmt"] = default_pix_fmt

        args = ["-c:v", codec]
        rate_control = dict(encode_config.get("rateControl", {}))
        mode = str(rate_control.get("mode") or "").strip()
        value = rate_control.get("value")

        if mode == "crf" and value is not None:
            args.extend(["-crf", str(value)])
        elif mode == "cq" and value is not None:
            args.extend(["-cq", str(value)])
        elif mode == "qp" and value is not None:
            args.extend(["-qp", str(value)])
        elif mode == "bitrate" and value is not None:
            args.extend(["-b:v", _format_bitrate(value)])

        args.extend(self._build_option_args(options))
        return args

    def build_encode_output_args(self, output_path: str, encode_config: dict[str, Any] | None = None) -> list[str]:
        args = self.build_encode_video_args(encode_config)
        args.extend([output_path, "-y"])
        return args

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def get_version(self) -> str | None:
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip().splitlines()[0] if result.stdout.strip() else None

    def _parse_supported_values(self, text: str, prefix: str) -> list[str]:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped.removeprefix(prefix).strip().split()
        return []

    def _build_option_args(self, options: dict[str, Any]) -> list[str]:
        args: list[str] = []
        for key, value in options.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            args.append(f"-{key}")
            if isinstance(value, bool):
                args.append("1" if value else "0")
            else:
                args.append(str(value))
        return args

    def _default_pix_fmt(self, codec: str) -> str | None:
        defaults = {
            "libx264": "yuv420p",
            "libx265": "yuv420p10le",
            "libaom-av1": "yuv420p10le",
            "libsvtav1": "yuv420p10le",
            "h264_nvenc": "yuv420p",
            "hevc_nvenc": "p010le",
            "av1_nvenc": "p010le",
            "h264_qsv": "nv12",
            "hevc_qsv": "p010le",
            "av1_qsv": "p010le",
        }
        return defaults.get(codec)

    def _run_command(self, cmd: list[str], *, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
        logger.debug("Running FFmpeg command: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"FFmpeg command failed ({result.returncode}): {message}")
        return result

    def _auto_detect_paths(self) -> None:
        if not self._ffmpeg_path_explicit and not os.path.isfile(self.ffmpeg_path):
            found = shutil.which("ffmpeg")
            if found:
                logger.info("Auto-detected ffmpeg at %s", found)
                self.ffmpeg_path = found

        if not self._ffprobe_path_explicit and not os.path.isfile(self.ffprobe_path):
            found = shutil.which("ffprobe")
            if found:
                logger.info("Auto-detected ffprobe at %s", found)
                self.ffprobe_path = found


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
