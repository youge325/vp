"""CLI entry point for ``python -m app check|info|process``."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any

from app.errors import ProcessError, ResumeConflictError

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.utils.onnx_models import resolve_onnx_model_path, scan_onnx_models
from app.config import settings
from app.planning import (
    build_signature,
    build_stage_plan,
    resolve_video_info,
    SegmentManifest,
)
from app.processing.anime_optimization import SUPPORTED_PROFILES as ANIME_PROFILES
from app.processing.interpolation import SUPPORTED_ALGORITHMS as INTERPOLATION_ALGORITHMS
from app.processing.streaming import process_video_streaming
from app.processing.super_resolution import SUPPORTED_ALGORITHMS as SR_ALGORITHMS
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.file_utils import get_output_path, validate_input_path
from app.utils.logger import get_logger, setup_logging
from app.utils.subprocess_utils import hidden_subprocess_kwargs
from app.utils.system_probe import list_gpu_adapters
from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig
from app.protocol import ndjson

logger = get_logger(__name__)


class TaskErrorCode(str, Enum):
    """Error codes synchronized with Rust protocol::TaskErrorCode."""

    MISSING_FFMPEG = "missing_ffmpeg"
    MISSING_MODEL = "missing_model"
    MISSING_TENSOR_BACKEND = "missing_tensor_backend"
    CANCELLED = "cancelled"
    PROCESS_FAILED = "process_failed"
    INVALID_INPUT = "invalid_input"
    INVALID_CONFIG = "invalid_config"
    RESUME_CONFLICT = "resume_conflict"


PROCESS_ORDER_MAP = {
    "super_resolution_then_interpolation": [
        "super_resolution",
        "frame_interpolation",
    ],
    "frame_interpolation_then_super_resolution": [
        "frame_interpolation",
        "super_resolution",
    ],
}

PROCESS_LABEL_MAP = {
    "frame_interpolation": "Frame Interpolation",
    "super_resolution": "Super Resolution",
    "anime_optimization": "Anime Optimization",
    "format_conversion": "Format Conversion",
    "frame_filter_chain": "Frame Filter Chain",
}
TERMINAL_PROGRESS_PREFIX = "[VP_PROGRESS]"
TERMINAL_PROGRESS_BAR_WIDTH = 24


def _emit_terminal(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _emit_error(
    code: TaskErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    exit_code: int | None = None,
) -> None:
    exc = ProcessError(code, message, details=details or {})
    if exit_code is not None:
        exc.exit_code = exit_code
    raise exc


def _load_json_arg(
    raw_value: str | None,
    default: dict[str, Any],
    model_cls: type,
) -> dict[str, Any]:
    if not raw_value:
        return default
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object.")
    merged = _deep_merge(default, payload)
    try:
        validated = model_cls.model_validate(merged)
    except Exception as exc:
        raise ValueError(f"Config validation failed for {model_cls.__name__}: {exc}") from exc
    return validated.model_dump(by_alias=True)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _model_path(model_version: str | None = None) -> Path:
    version = model_version or settings.RIFE_MODEL_VERSION
    return Path(settings.RIFE_MODEL_DIR) / f"flownet_v{version}.pkl"


def _processing_needs_interpolation(processing_steps: list[dict[str, Any]]) -> bool:
    return any(step["algorithm_type"] == "frame_interpolation" for step in processing_steps)


def _default_decode_config() -> dict[str, Any]:
    return {
        "mode": "software",
        "hwaccel": "",
        "decoder": "software",
        "options": {},
    }


def _default_encode_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "codec": args.codec,
        "family": "cpu",
        "container": "mp4",
        "keepAudio": True,
        "rateControl": {
            "mode": "crf",
            "value": args.crf,
        },
        "options": {
            "preset": args.preset,
        },
    }


def _default_workflow_config(args: argparse.Namespace) -> dict[str, Any]:
    enable_interpolation = args.enable_interpolation or args.algorithm == "frame_interpolation"
    enable_super_resolution = args.enable_super_resolution or args.algorithm == "super_resolution"
    enable_anime = args.algorithm == "anime_optimization"
    return {
        "fpsMode": args.fps_mode,
        "processOrder": args.process_order,
        "interpolation": {
            "enabled": enable_interpolation,
            "targetFps": args.target_fps,
            "multi": args.multi,
            "model": args.model,
            "onnxModel": "",
            "scale": args.scale,
            "fp16": args.fp16,
            "tensorBackend": args.backend,
        },
        "superResolution": {
            "enabled": enable_super_resolution,
            "scaleFactor": args.sr_scale_factor,
            "algorithm": args.sr_algorithm,
            "onnxModel": "",
        },
        "anime": {
            "enabled": enable_anime,
            "profile": "clean-lines",
            "denoise": 10,
            "edgeBoost": 15,
        },
        "preprocess": {
            "enabled": False,
            "filters": [],
        },
        "postprocess": {
            "enabled": False,
            "filters": [],
        },
    }


def _default_output_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "outputDir": args.output_dir or settings.OUTPUT_DIR,
        "openOnComplete": True,
        "segmentFrames": 1000,
    }


def _resolve_primary_algorithm(workflow_config: dict[str, Any]) -> str:
    if workflow_config["interpolation"]["enabled"]:
        return "frame_interpolation"
    if workflow_config["superResolution"]["enabled"]:
        return "super_resolution"
    if workflow_config["anime"]["enabled"]:
        return "anime_optimization"
    return "format_conversion"


def _build_algorithm_kwargs(workflow_config: dict[str, Any], algorithm_type: str) -> dict[str, Any]:
    interpolation = workflow_config["interpolation"]
    super_resolution = workflow_config["superResolution"]
    if algorithm_type == "frame_interpolation":
        return {
            "multi": interpolation["multi"],
            "model_version": interpolation["model"],
            "scale": interpolation["scale"],
            "fp16": interpolation["fp16"],
            "onnx_model": interpolation.get("onnxModel") or interpolation.get("onnx_model"),
            "engine": interpolation.get("engine") or "cuda",
        }
    if algorithm_type == "super_resolution":
        return {
            "scale_factor": super_resolution["scaleFactor"],
            "sr_algorithm": super_resolution["algorithm"],
            "onnx_model": super_resolution.get("onnxModel") or super_resolution.get("onnx_model"),
            "engine": super_resolution.get("engine") or "cuda",
        }
    if algorithm_type == "frame_filter_chain":
        return {}
    return {}


def _resolve_processing_steps(config_or_args: dict[str, Any] | argparse.Namespace) -> list[dict[str, Any]]:
    if isinstance(config_or_args, argparse.Namespace):
        workflow_config = _default_workflow_config(config_or_args)
        algorithm = config_or_args.algorithm
    else:
        workflow_config = config_or_args
        algorithm = _resolve_primary_algorithm(workflow_config)

    enable_interpolation = bool(workflow_config["interpolation"]["enabled"])
    enable_super_resolution = bool(workflow_config["superResolution"]["enabled"])

    if enable_interpolation or enable_super_resolution:
        if enable_interpolation and enable_super_resolution:
            algorithm_types = PROCESS_ORDER_MAP[workflow_config["processOrder"]]
        elif enable_interpolation:
            algorithm_types = ["frame_interpolation"]
        else:
            algorithm_types = ["super_resolution"]
    elif algorithm == "format_conversion":
        algorithm_types = []
    else:
        algorithm_types = [algorithm]

    steps: list[dict[str, Any]] = []

    # Prepend preprocess filter chain if enabled
    if workflow_config.get("preprocess", {}).get("enabled"):
        steps.append(
            {
                "algorithm_type": "frame_filter_chain",
                "algorithm_kwargs": {"filters": workflow_config["preprocess"]["filters"]},
                "stage_name": f"{len(steps) + 1:02d}_preprocess",
            }
        )

    for algorithm_type in algorithm_types:
        steps.append(
            {
                "algorithm_type": algorithm_type,
                "algorithm_kwargs": _build_algorithm_kwargs(workflow_config, algorithm_type),
                "stage_name": f"{len(steps) + 1:02d}_{algorithm_type}",
            }
        )

    # Append postprocess filter chain if enabled
    if workflow_config.get("postprocess", {}).get("enabled"):
        steps.append(
            {
                "algorithm_type": "frame_filter_chain",
                "algorithm_kwargs": {"filters": workflow_config["postprocess"]["filters"]},
                "stage_name": f"{len(steps) + 1:02d}_postprocess",
            }
        )

    return steps


def _resolve_fps_and_multi(
    workflow_config: dict[str, Any],
    ffmpeg: FFmpegWrapper,
    input_path: str,
) -> tuple[int, float, float | None, bool]:
    interpolation = workflow_config["interpolation"]
    fps_mode = workflow_config.get("fpsMode", "multi")

    if fps_mode == "target":
        target_fps = float(interpolation.get("targetFps") or 60.0)
        source_fps = ffmpeg.get_fps(input_path)
        multi = max(2, math.ceil(target_fps / source_fps))
        interpolated_fps = source_fps * multi
        need_resample = interpolated_fps > target_fps
        encode_fps = target_fps if need_resample else interpolated_fps
        return multi, encode_fps, interpolated_fps, need_resample

    source_fps = ffmpeg.get_fps(input_path)
    multi = int(interpolation.get("multi") or settings.RIFE_DEFAULT_MULTI)
    encode_fps = source_fps * multi if interpolation.get("enabled") else source_fps
    return multi, encode_fps, None, False


def _resolve_expected_output_frames(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    workflow_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    final_output_fps: float | None,
) -> int:
    source_frames = ffmpeg.get_frame_count(input_path)
    if source_frames <= 0:
        return 1
    if final_output_fps is not None:
        duration = ffmpeg.get_duration(input_path)
        if duration > 0:
            return max(1, int(round(duration * final_output_fps)))
    if not _processing_needs_interpolation(processing_steps):
        return source_frames

    multi = int(workflow_config["interpolation"].get("multi") or settings.RIFE_DEFAULT_MULTI)
    if source_frames < 2:
        return source_frames
    return source_frames + (source_frames - 1) * (multi - 1)


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
    filled = round(ratio * TERMINAL_PROGRESS_BAR_WIDTH)
    return f"[{'#' * filled}{'-' * (TERMINAL_PROGRESS_BAR_WIDTH - filled)}]"


class CliProgressReporter:
    def __init__(self, total_frames: int):
        self.total_frames = max(int(total_frames), 1)
        self.current_frame = 0
        self.started_at = time.time()
        self._last_reported_percent = -1.0

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
        _emit_terminal(
            f"{TERMINAL_PROGRESS_PREFIX} "
            f"{_format_progress_bar(display_current, self.total_frames)} "
            f"{percent:5.1f}% "
            f"{display_current}/{self.total_frames} "
            f"| {fps_text} "
            f"| {speed_text} "
            f"| ETA {_format_eta(eta_seconds)}"
        )
        ndjson.progress(
            current=display_current,
            total=self.total_frames,
            percent=round(percent, 1),
            stage="Encoding",
            stage_index=1,
            stage_total=1,
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


def _resolve_processed_frame_count(ffmpeg: FFmpegWrapper, output_path: str, fallback: int) -> int:
    try:
        return ffmpeg.get_frame_count(output_path) or fallback
    except Exception:  # pragma: no cover - fallback for defensive CLI reporting
        return fallback


def _check_pytorch_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'pytorch_available': False, 'gpu_available': False, 'gpu_devices': [], "
        "          'supports_cuda': False, 'supports_tensorrt': False}\n"
        "try:\n"
        "    import torch\n"
        "    result['pytorch_available'] = True\n"
        "    if torch.cuda.is_available():\n"
        "        result['gpu_available'] = True\n"
        "        result['gpu_devices'] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]\n"
        "        result['supports_cuda'] = True\n"
        "        result['supports_tensorrt'] = True\n"
        "except (ImportError, OSError):\n"
        "    pass\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [settings.PYTHON_EXECUTABLE, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {
        "pytorch_available": False,
        "gpu_available": False,
        "gpu_devices": [],
        "supports_cuda": False,
        "supports_tensorrt": False,
    }


def _check_paddle_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'paddle_available': False, 'supports_cuda': False, "
        "          'supports_tensorrt': False, 'supports_dcu': False}\n"
        "try:\n"
        "    import paddle\n"
        "    result['paddle_available'] = True\n"
        "    if paddle.device.is_compiled_with_cuda():\n"
        "        result['supports_cuda'] = True\n"
        "        result['supports_tensorrt'] = True\n"
        "    if paddle.device.is_compiled_with_rocm():\n"
        "        result['supports_dcu'] = True\n"
        "except (ImportError, OSError):\n"
        "    pass\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [settings.PYTHON_EXECUTABLE, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {"paddle_available": False, "supports_cuda": False, "supports_tensorrt": False, "supports_dcu": False}


def _check_onnxruntime_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'onnx_available': False, 'providers': [], "
        "          'supports_cuda': False, 'supports_tensorrt': False}\n"
        "try:\n"
        "    import onnxruntime as ort\n"
        "    result['onnx_available'] = True\n"
        "    providers = ort.get_available_providers()\n"
        "    result['providers'] = providers\n"
        "    result['supports_cuda'] = 'CUDAExecutionProvider' in providers\n"
        "    # 有 CUDA provider 说明是 NVIDIA GPU，默认同时支持 TensorRT\n"
        "    result['supports_tensorrt'] = 'TensorrtExecutionProvider' in providers or 'CUDAExecutionProvider' in providers\n"
        "except (ImportError, OSError):\n"
        "    pass\n"
        "print(json.dumps(result), flush=True)\n"
    )
    try:
        proc = subprocess.run(
            [settings.PYTHON_EXECUTABLE, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {"onnx_available": False, "providers": [], "supports_cuda": False, "supports_tensorrt": False}


def _validate_onnx_models_for_workflow(
    workflow_config: dict[str, Any],
    processing_steps: list[dict[str, Any]],
    tensor_backend_name: str,
) -> None:
    if tensor_backend_name != "onnx":
        return

    for step in processing_steps:
        if step["algorithm_type"] == "frame_interpolation":
            model_name = _get_onnx_model_name(workflow_config["interpolation"])
            algorithm = workflow_config["interpolation"].get("algorithm", "rife")
            resolve_onnx_model_path("interpolation", algorithm, model_name, model_root=settings.RIFE_MODEL_DIR)
        elif step["algorithm_type"] == "super_resolution":
            model_name = _get_onnx_model_name(workflow_config["superResolution"])
            algorithm = workflow_config["superResolution"].get("algorithm", "placeholder")
            resolve_onnx_model_path("super_resolution", algorithm, model_name, model_root=settings.RIFE_MODEL_DIR)


def _get_onnx_model_name(config: dict[str, Any]) -> str | None:
    return config.get("onnxModel") or config.get("onnx_model")


def cmd_process(args: argparse.Namespace) -> None:
    input_path = args.input
    if not validate_input_path(input_path):
        _emit_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        _emit_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )

    try:
        decode_config = _load_json_arg(args.decode_config_json, _default_decode_config(), DecodeConfig)
        encode_config = _load_json_arg(args.encode_config_json, _default_encode_config(args), EncodeConfig)
        workflow_config = _load_json_arg(args.workflow_config_json, _default_workflow_config(args), WorkflowConfig)
        output_config = _load_json_arg(args.output_config_json, _default_output_config(args), OutputConfig)
    except ValueError as exc:
        _emit_error(TaskErrorCode.INVALID_CONFIG, str(exc))

    processing_steps = _resolve_processing_steps(workflow_config)
    tensor_backend_name = workflow_config["interpolation"].get("tensorBackend", args.backend)
    if _processing_needs_interpolation(processing_steps):
        if tensor_backend_name == "onnx":
            try:
                _validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name)
            except FileNotFoundError as exc:
                _emit_error(
                    TaskErrorCode.MISSING_MODEL,
                    str(exc),
                    details={
                        "tensor_backend": tensor_backend_name,
                        "model_root": settings.RIFE_MODEL_DIR,
                    },
                )
        else:
            model_path = _model_path(workflow_config["interpolation"]["model"])
            if not model_path.is_file() or model_path.stat().st_size == 0:
                _emit_error(
                    TaskErrorCode.MISSING_MODEL,
                    f"Default interpolation model is missing: {model_path}",
                    details={
                        "model_path": str(model_path),
                        "model_version": workflow_config["interpolation"]["model"],
                    },
                )
    elif tensor_backend_name == "onnx":
        try:
            _validate_onnx_models_for_workflow(workflow_config, processing_steps, tensor_backend_name)
        except FileNotFoundError as exc:
            _emit_error(
                TaskErrorCode.MISSING_MODEL,
                str(exc),
                details={
                    "tensor_backend": tensor_backend_name,
                    "model_root": settings.RIFE_MODEL_DIR,
                },
            )

    output_dir = output_config.get("outputDir") or settings.OUTPUT_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.RIFE_MODEL_DIR).mkdir(parents=True, exist_ok=True)

    container = str(encode_config.get("container") or "mp4")
    if args.output:
        output_path = args.output
        Path(output_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")

    multi, encode_fps, _interpolated_fps, need_resample = _resolve_fps_and_multi(workflow_config, ffmpeg, input_path)
    workflow_config["interpolation"]["multi"] = multi
    final_output_fps = encode_fps if need_resample else None
    expected_output_frames = _resolve_expected_output_frames(
        ffmpeg=ffmpeg,
        input_path=input_path,
        workflow_config=workflow_config,
        processing_steps=processing_steps,
        final_output_fps=final_output_fps,
    )
    progress_reporter = CliProgressReporter(expected_output_frames)

    # 为每个处理步骤生成进度回调，把源帧索引透传给编码进度条。
    # 百分比会与最终输出帧数不完全对齐，但至少能让前端看到进度在动。
    progress_callbacks = [
        lambda current, total, reporter=progress_reporter: reporter.update(current) for _ in processing_steps
    ]
    start_time = time.time()
    try:
        if processing_steps:
            result = process_video_streaming(
                ffmpeg=ffmpeg,
                input_path=input_path,
                output_path=output_path,
                decode_config=decode_config,
                encode_config=encode_config,
                workflow_config=workflow_config,
                output_config=output_config,
                processing_steps=processing_steps,
                tensor_backend_name=tensor_backend_name,
                progress_callbacks=progress_callbacks,
                output_fps=final_output_fps,
                encode_progress_callback=progress_reporter.update,
                resume_mode=getattr(args, "resume_mode", "auto"),
            )
        else:
            _enforce_format_conversion_resume_mode(
                output_path=output_path,
                resume_mode=getattr(args, "resume_mode", "auto"),
            )
            ffmpeg.transcode_video(
                input_path=input_path,
                output_path=output_path,
                decode_config=decode_config,
                encode_config=encode_config,
                progress_callback=lambda progress: progress_reporter.update(
                    int(progress.get("frame") or 0),
                    progress.get("fps"),
                    progress.get("speed"),
                    progress.get("out_time_seconds"),
                    str(progress.get("progress") or ""),
                ),
            )
            result = {
                "output_path": output_path,
                "processed_frames": _resolve_processed_frame_count(ffmpeg, output_path, expected_output_frames),
                "audio_merged": bool(encode_config.get("keepAudio", True)),
            }

        elapsed = round(time.time() - start_time, 2)
        processed_frames = _resolve_processed_frame_count(
            ffmpeg,
            str(result.get("output_path", output_path)),
            int(result.get("processed_frames", expected_output_frames) or expected_output_frames),
        )
        progress_reporter.finish(processed_frames)
        ndjson.completed(
            output_path=result.get("output_path", output_path),
            processed_frames=processed_frames,
            time_seconds=elapsed,
        )
    except KeyboardInterrupt:
        raise ProcessError(
            TaskErrorCode.CANCELLED,
            "Processing was cancelled by the user.",
            details={"input_path": input_path},
        )
    except ResumeConflictError as exc:
        raise ProcessError(
            TaskErrorCode.RESUME_CONFLICT,
            "An existing output was detected; please choose how to proceed.",
            details={
                "input_path": input_path,
                **exc.to_details(),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details.update(
            {
                "input_path": input_path,
                "output_path": output_path,
                "algorithm": _resolve_primary_algorithm(workflow_config),
                "processing_steps": [step["algorithm_type"] for step in processing_steps],
            }
        )
        raise pe


def _enforce_format_conversion_resume_mode(*, output_path: str, resume_mode: str) -> None:
    """Apply resume_mode semantics for the format-conversion fast path.

    The streaming pipeline owns its own conflict logic via ``SegmentManifest``;
    format-only conversions skip the sidecar entirely, so they need a
    miniature equivalent here so a stale output is not silently overwritten.
    """
    target = Path(output_path)
    if not target.exists():
        return
    if resume_mode in {"force-fresh", "force-resume"}:
        target.unlink(missing_ok=True)
        return
    raise ResumeConflictError(
        output_path=str(target.resolve()),
        completed_chunks=0,
        completed_output_frames=0,
        sidecar_signature_match=False,
    )


def cmd_inspect_output(args: argparse.Namespace) -> None:
    """Probe whether a final output and resume sidecar exist for a planned run.

    Pure read-only inspection. Returns a JSON payload describing whether the
    final output already exists, whether a sidecar is present and matches the
    planned signature, and how much progress (chunks / output frames) the
    sidecar represents. Used by the Tauri host as a pre-flight before
    spawning ``process``.
    """
    input_path = args.input
    if not validate_input_path(input_path):
        _emit_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        _emit_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )

    try:
        decode_config = _load_json_arg(args.decode_config_json, _default_decode_config(), DecodeConfig)
        encode_config = _load_json_arg(args.encode_config_json, _default_encode_config(args), EncodeConfig)
        workflow_config = _load_json_arg(args.workflow_config_json, _default_workflow_config(args), WorkflowConfig)
        output_config = _load_json_arg(args.output_config_json, _default_output_config(args), OutputConfig)
    except ValueError as exc:
        _emit_error(TaskErrorCode.INVALID_CONFIG, str(exc))

    processing_steps = _resolve_processing_steps(workflow_config)

    output_dir = output_config.get("outputDir") or settings.OUTPUT_DIR
    container = str(encode_config.get("container") or "mp4")
    if args.output:
        output_path = args.output
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")

    multi, encode_fps, _interpolated_fps, need_resample = _resolve_fps_and_multi(workflow_config, ffmpeg, input_path)
    workflow_config["interpolation"]["multi"] = multi
    final_output_fps = encode_fps if need_resample else None

    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        processing_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=final_output_fps,
    )

    if processing_steps:
        signature = build_signature(
            input_path=input_path,
            output_path=output_path,
            decode_config=decode_config,
            encode_config=encode_config,
            workflow_config=workflow_config,
            output_config=output_config,
            processing_steps=processing_steps,
            video_info=video_info,
        )
        manifest = SegmentManifest(output_path)
        info = manifest.inspect(
            signature,
            total_output_frames=stage_plan.total_encoded_frames,
        )
    else:
        # Format conversion path has no sidecar; only the final-file check matters.
        resolved_output = Path(output_path).expanduser().resolve()
        info = {
            "outputPath": str(resolved_output),
            "finalExists": resolved_output.exists(),
            "sidecarExists": False,
            "signatureMatch": False,
            "completedChunks": 0,
            "completedOutputFrames": 0,
            "nextSourceFrame": 0,
            "totalOutputFrames": stage_plan.total_encoded_frames,
        }

    info["input_path"] = input_path
    info["pipeline_kind"] = "streaming" if processing_steps else "format_conversion"
    ndjson.resume_inspection(**info)


def cmd_info(args: argparse.Namespace) -> None:
    input_path = args.input
    if not os.path.isfile(input_path):
        _emit_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file does not exist: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        _emit_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )

    try:
        info = ffmpeg.get_video_info(input_path)
        fps = ffmpeg.get_fps(input_path)
        frames = ffmpeg.get_frame_count(input_path)
        duration = ffmpeg.get_duration(input_path)
        has_audio = ffmpeg.has_audio(input_path)
        video_codec = ffmpeg.get_primary_video_codec(input_path)

        width = 0
        height = 0
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                break

        ndjson.info(
            fps=fps,
            frames=frames,
            duration=duration,
            hasAudio=has_audio,
            width=width,
            height=height,
            videoCodec=video_codec,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        if isinstance(exc, ProcessError):
            raise
        pe = ProcessError.from_exception(exc)
        pe.details["input_path"] = input_path
        raise pe


def cmd_check(_args: argparse.Namespace) -> None:
    ffmpeg = FFmpegWrapper()
    ffmpeg_available = ffmpeg.is_available()
    ffmpeg_version = ffmpeg.get_version() if ffmpeg_available else ""

    pytorch_result = _check_pytorch_in_subprocess()
    paddle_result = _check_paddle_in_subprocess()
    onnx_result = _check_onnxruntime_in_subprocess()
    gpu_adapters = list_gpu_adapters()
    non_virtual_adapters = [adapter for adapter in gpu_adapters if adapter.get("device_type") != "virtual"]

    default_model_path = Path(settings.RIFE_MODEL_DIR) / "interpolation" / "rife" / "rife_v4.25.onnx"
    default_model_available = default_model_path.is_file() and default_model_path.stat().st_size > 0
    onnx_models = scan_onnx_models(settings.RIFE_MODEL_DIR)
    ffmpeg_capabilities = (
        ffmpeg.discover_capabilities(gpu_adapters)
        if ffmpeg_available
        else {
            "hwaccels": [],
            "encoderProfiles": [],
            "decoderProfiles": [],
        }
    )

    # 构建推理引擎支持信息
    tensor_engines: dict[str, list[str]] = {}
    if pytorch_result.get("pytorch_available"):
        engines = []
        if pytorch_result.get("supports_cuda"):
            engines.append("cuda")
        if pytorch_result.get("supports_tensorrt"):
            engines.append("tensorrt")
        tensor_engines["pytorch"] = engines
    if paddle_result.get("paddle_available"):
        engines = []
        if paddle_result.get("supports_cuda"):
            engines.append("cuda")
        if paddle_result.get("supports_tensorrt"):
            engines.append("tensorrt")
        if paddle_result.get("supports_dcu"):
            engines.append("dcu")
        tensor_engines["paddle"] = engines
    if onnx_result.get("onnx_available"):
        engines = []
        if onnx_result.get("supports_tensorrt"):
            engines.append("tensorrt")
        if onnx_result.get("supports_cuda"):
            engines.append("cuda")
        tensor_engines["onnx"] = engines

    # 构建后端设备兼容性矩阵
    backend_device_support: dict[str, list[str]] = {
        "pytorch": ["nvidia", "intel", "amd"],
        "paddle": ["nvidia", "intel", "amd", "hygon"],
        "onnx": ["nvidia", "intel", "amd"],
    }

    interpolation_algorithms_payload = [
        {**alg, "onnxModels": onnx_models.get("interpolation", {}).get(alg["name"], [])}
        for alg in INTERPOLATION_ALGORITHMS
    ]
    super_resolution_algorithms_payload = [
        {**alg, "onnxModels": onnx_models.get("super_resolution", {}).get(alg["name"], [])} for alg in SR_ALGORITHMS
    ]

    ndjson.check(
        ffmpeg={
            "available": ffmpeg_available,
            "path": ffmpeg.ffmpeg_path,
            "ffprobePath": ffmpeg.ffprobe_path,
            "version": ffmpeg_version,
            "hwaccels": ffmpeg_capabilities["hwaccels"],
            "encoderProfiles": ffmpeg_capabilities["encoderProfiles"],
            "decoderProfiles": ffmpeg_capabilities["decoderProfiles"],
        },
        gpu={
            "available": bool(non_virtual_adapters),
            "devices": [adapter["name"] for adapter in non_virtual_adapters],
            "adapters": gpu_adapters,
            "cudaAvailable": pytorch_result["gpu_available"],
        },
        tensorBackends={
            "pytorch": pytorch_result["pytorch_available"],
            "paddle": paddle_result["paddle_available"],
            "onnx": onnx_result["onnx_available"],
        },
        tensorEngines=tensor_engines,
        backendDeviceSupport=backend_device_support,
        onnxRuntime={
            "available": onnx_result["onnx_available"],
            "providers": onnx_result["providers"],
        },
        rifeModel={
            "available": default_model_available,
            "version": settings.RIFE_MODEL_VERSION,
            "path": str(default_model_path),
        },
        interpolationAlgorithms=interpolation_algorithms_payload,
        superResolutionAlgorithms=super_resolution_algorithms_payload,
        animeProfiles=ANIME_PROFILES,
        runtime={
            "mode": settings.runtime_mode,
            "bundled": settings.bundled_runtime_available,
            "pythonExecutable": settings.PYTHON_EXECUTABLE,
            "defaultModelAvailable": default_model_available,
        },
        resources=settings.resource_summary(),
    )


def _add_shared_planning_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments common to ``process`` and ``inspect-output`` subcommands.

    Keeps the parser definitions in sync so a change to one command's CLI
    surface is automatically reflected in the other.
    """
    parser.add_argument("--decode-config-json", default=None, help="Nested decode config JSON")
    parser.add_argument("--encode-config-json", default=None, help="Nested encode config JSON")
    parser.add_argument("--workflow-config-json", default=None, help="Nested workflow config JSON")
    parser.add_argument("--output-config-json", default=None, help="Nested output config JSON")
    parser.add_argument(
        "--algorithm",
        default="frame_interpolation",
        choices=[
            "frame_interpolation",
            "super_resolution",
            "anime_optimization",
            "format_conversion",
        ],
        help="Primary algorithm to run",
    )
    parser.add_argument("--enable-interpolation", action="store_true", help="Enable interpolation stage")
    parser.add_argument("--enable-super-resolution", action="store_true", help="Enable super-resolution stage")
    parser.add_argument(
        "--process-order",
        default="super_resolution_then_interpolation",
        choices=list(PROCESS_ORDER_MAP.keys()),
        help="Stage order when interpolation and super-resolution are both enabled",
    )
    parser.add_argument("--fps", type=float, default=60.0, help="Default output FPS")
    parser.add_argument("--fps-mode", default="multi", choices=["multi", "target"], help="FPS calculation mode")
    parser.add_argument("--target-fps", type=float, default=60.0, help="Target FPS when using target mode")
    parser.add_argument("--codec", default="libx264", help="Video codec")
    parser.add_argument("--crf", type=int, default=18, help="CRF quality")
    parser.add_argument("--preset", default="medium", help="Encoding preset")
    parser.add_argument("--backend", default="pytorch", choices=["pytorch", "paddle", "onnx"], help="Tensor backend")
    parser.add_argument("--output-dir", default=None, help="Output directory override")
    parser.add_argument("--multi", type=int, default=2, help="Interpolation multiplier")
    parser.add_argument("--model", default="4.25", help="RIFE model version")
    parser.add_argument("--scale", type=float, default=1.0, help="Interpolation scale factor")
    parser.add_argument("--fp16", action="store_true", help="Enable FP16 inference")
    parser.add_argument("--sr-scale-factor", type=float, default=2.0, help="Super-resolution scale")
    parser.add_argument("--sr-algorithm", default="placeholder", help="Super-resolution algorithm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="Video Processing Workbench CLI",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    process_parser = subcommands.add_parser("process", help="Run the processing pipeline")
    process_parser.add_argument("--input", required=True, help="Input video path")
    process_parser.add_argument("--output", default=None, help="Optional output file path")
    _add_shared_planning_args(process_parser)
    process_parser.add_argument(
        "--resume-mode",
        default="auto",
        choices=["auto", "force-fresh", "force-resume"],
        help=(
            "Conflict policy when an existing output is detected. 'auto' (default) "
            "resumes on signature match, otherwise emits a resume_conflict error so "
            "the caller can prompt the user. 'force-fresh' wipes both the sidecar "
            "and the existing final file. 'force-resume' keeps the sidecar."
        ),
    )
    process_parser.set_defaults(func=cmd_process)

    info_parser = subcommands.add_parser("info", help="Inspect an input video")
    info_parser.add_argument("--input", required=True, help="Input video path")
    info_parser.set_defaults(func=cmd_info)

    inspect_output_parser = subcommands.add_parser(
        "inspect-output",
        help="Probe whether a final output and resume sidecar already exist for a planned run.",
    )
    inspect_output_parser.add_argument("--input", required=True, help="Input video path")
    inspect_output_parser.add_argument("--output", default=None, help="Optional explicit output file path")
    _add_shared_planning_args(inspect_output_parser)
    inspect_output_parser.set_defaults(func=cmd_inspect_output)

    check_parser = subcommands.add_parser("check", help="Inspect runtime availability")
    check_parser.set_defaults(func=cmd_check)

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    try:
        args = parser.parse_args()
        args.func(args)
    except KeyboardInterrupt:
        _emit_error(TaskErrorCode.CANCELLED, "Operation cancelled by the user.", exit_code=130)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        logger.exception("Unhandled backend CLI failure")
        pe = ProcessError.from_exception(exc)
        _emit_error(
            pe.code,
            pe.message,
            details={**pe.details, "exception": exc.__class__.__name__},
        )


if __name__ == "__main__":
    main()
