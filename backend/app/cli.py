"""CLI entry point for ``python -m app check|info|process``."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.algorithms.factory import register_default_algorithms
from app.config import settings
from app.processing.streaming import process_video_streaming
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.file_utils import get_output_path, validate_input_path
from app.utils.logger import get_logger, setup_logging
from app.utils.system_probe import list_gpu_adapters

logger = get_logger(__name__)


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
}


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _emit_error(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    exit_code: int = 1,
) -> None:
    _emit(
        {
            "type": "error",
            "code": code,
            "message": message,
            "details": details or {},
        }
    )
    raise SystemExit(exit_code)


def _load_json_arg(raw_value: str | None, default: dict[str, Any]) -> dict[str, Any]:
    if not raw_value:
        return default
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object.")
    return _deep_merge(default, payload)


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


def _infer_error_code(exc: BaseException) -> str:
    message = str(exc).lower()
    if isinstance(exc, FileNotFoundError):
        if "ffmpeg" in message or "ffprobe" in message:
            return "missing_ffmpeg"
        if "flownet_v" in message or "model" in message:
            return "missing_model"
    if "ffmpeg" in message or "ffprobe" in message:
        return "missing_ffmpeg"
    if "flownet_v" in message or "model" in message:
        return "missing_model"
    if "cancelled" in message or "canceled" in message:
        return "cancelled"
    return "process_failed"


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
            "scale": args.scale,
            "fp16": args.fp16,
            "tensorBackend": args.backend,
        },
        "superResolution": {
            "enabled": enable_super_resolution,
            "scaleFactor": args.sr_scale_factor,
            "algorithm": args.sr_algorithm,
        },
        "anime": {
            "enabled": enable_anime,
            "profile": "clean-lines",
            "denoise": 10,
            "edgeBoost": 15,
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
        }
    if algorithm_type == "super_resolution":
        return {
            "scale_factor": super_resolution["scaleFactor"],
            "sr_algorithm": super_resolution["algorithm"],
        }
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
    for index, algorithm_type in enumerate(algorithm_types, start=1):
        steps.append(
            {
                "algorithm_type": algorithm_type,
                "algorithm_kwargs": _build_algorithm_kwargs(workflow_config, algorithm_type),
                "stage_name": f"{index:02d}_{algorithm_type}",
            }
        )
    return steps


def _make_progress_callback(stage_index: int, total_stages: int, algorithm_type: str):
    def progress_callback(current: int, total: int) -> None:
        stage_fraction = (current / total) if total > 0 else 0.0
        overall_percent = ((stage_index + stage_fraction) / total_stages) * 100 if total_stages > 0 else 0.0
        _emit(
            {
                "type": "progress",
                "current": current,
                "total": total,
                "percent": round(overall_percent, 1),
                "stage": PROCESS_LABEL_MAP.get(algorithm_type, algorithm_type),
                "stage_index": stage_index + 1,
                "stage_total": total_stages,
            }
        )

    return progress_callback


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


def _check_pytorch_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'pytorch_available': False, 'gpu_available': False, 'gpu_devices': []}\n"
        "try:\n"
        "    import torch\n"
        "    result['pytorch_available'] = True\n"
        "    if torch.cuda.is_available():\n"
        "        result['gpu_available'] = True\n"
        "        result['gpu_devices'] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]\n"
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
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {"pytorch_available": False, "gpu_available": False, "gpu_devices": []}


def _check_paddle_in_subprocess() -> dict[str, Any]:
    script = (
        "import json\n"
        "result = {'paddle_available': False}\n"
        "try:\n"
        "    import paddle\n"
        "    result['paddle_available'] = True\n"
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
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {"paddle_available": False}


def cmd_process(args: argparse.Namespace) -> None:
    register_default_algorithms()

    input_path = args.input
    if not validate_input_path(input_path):
        _emit_error(
            "invalid_input",
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        _emit_error(
            "missing_ffmpeg",
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )

    try:
        decode_config = _load_json_arg(args.decode_config_json, _default_decode_config())
        encode_config = _load_json_arg(args.encode_config_json, _default_encode_config(args))
        workflow_config = _load_json_arg(args.workflow_config_json, _default_workflow_config(args))
        output_config = _load_json_arg(args.output_config_json, _default_output_config(args))
    except ValueError as exc:
        _emit_error("invalid_config", str(exc))

    processing_steps = _resolve_processing_steps(workflow_config)
    if _processing_needs_interpolation(processing_steps):
        model_path = _model_path(workflow_config["interpolation"]["model"])
        if not model_path.is_file() or model_path.stat().st_size == 0:
            _emit_error(
                "missing_model",
                f"Default interpolation model is missing: {model_path}",
                details={
                    "model_path": str(model_path),
                    "model_version": workflow_config["interpolation"]["model"],
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

    tensor_backend_name = workflow_config["interpolation"].get("tensorBackend", args.backend)
    progress_callbacks = [
        _make_progress_callback(stage_index, len(processing_steps), step["algorithm_type"])
        for stage_index, step in enumerate(processing_steps)
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
                output_fps=encode_fps if need_resample else None,
            )
        else:
            ffmpeg.transcode_video(
                input_path=input_path,
                output_path=output_path,
                decode_config=decode_config,
                encode_config=encode_config,
            )
            result = {
                "output_path": output_path,
                "processed_frames": ffmpeg.get_frame_count(input_path),
                "audio_merged": bool(encode_config.get("keepAudio", True)),
            }

        elapsed = round(time.time() - start_time, 2)
        _emit(
            {
                "type": "completed",
                "output_path": result.get("output_path", output_path),
                "processed_frames": result.get("processed_frames", 0),
                "time_seconds": elapsed,
            }
        )
    except KeyboardInterrupt:
        _emit_error(
            "cancelled",
            "Processing was cancelled by the user.",
            details={"input_path": input_path},
            exit_code=130,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        _emit_error(
            _infer_error_code(exc),
            str(exc),
            details={
                "input_path": input_path,
                "output_path": output_path,
                "algorithm": _resolve_primary_algorithm(workflow_config),
                "processing_steps": [step["algorithm_type"] for step in processing_steps],
            },
        )


def cmd_info(args: argparse.Namespace) -> None:
    input_path = args.input
    if not os.path.isfile(input_path):
        _emit_error(
            "invalid_input",
            f"Input file does not exist: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        _emit_error(
            "missing_ffmpeg",
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

        _emit(
            {
                "type": "info",
                "fps": fps,
                "frames": frames,
                "duration": duration,
                "has_audio": has_audio,
                "width": width,
                "height": height,
                "video_codec": video_codec,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        _emit_error(
            _infer_error_code(exc),
            str(exc),
            details={"input_path": input_path},
        )


def cmd_check(_args: argparse.Namespace) -> None:
    ffmpeg = FFmpegWrapper()
    ffmpeg_available = ffmpeg.is_available()
    ffmpeg_version = ffmpeg.get_version() if ffmpeg_available else ""

    pytorch_result = _check_pytorch_in_subprocess()
    paddle_result = _check_paddle_in_subprocess()
    gpu_adapters = list_gpu_adapters()
    non_virtual_adapters = [adapter for adapter in gpu_adapters if adapter.get("device_type") != "virtual"]

    default_model_path = _model_path()
    default_model_available = default_model_path.is_file() and default_model_path.stat().st_size > 0
    ffmpeg_capabilities = (
        ffmpeg.discover_capabilities(gpu_adapters)
        if ffmpeg_available
        else {
            "hwaccels": [],
            "encoderProfiles": [],
            "decoderProfiles": [],
        }
    )

    _emit(
        {
            "type": "check",
            "ffmpeg": {
                "available": ffmpeg_available,
                "path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
                "version": ffmpeg_version,
                "hwaccels": ffmpeg_capabilities["hwaccels"],
                "encoderProfiles": ffmpeg_capabilities["encoderProfiles"],
                "decoderProfiles": ffmpeg_capabilities["decoderProfiles"],
            },
            "gpu": {
                "available": bool(non_virtual_adapters),
                "devices": [adapter["name"] for adapter in non_virtual_adapters],
                "adapters": gpu_adapters,
                "cuda_available": pytorch_result["gpu_available"],
            },
            "tensor_backends": {
                "pytorch": pytorch_result["pytorch_available"],
                "paddle": paddle_result["paddle_available"],
            },
            "rife_model": {
                "available": default_model_available,
                "version": settings.RIFE_MODEL_VERSION,
                "path": str(default_model_path),
            },
            "runtime": {
                "mode": settings.runtime_mode,
                "bundled": settings.bundled_runtime_available,
                "python_executable": settings.PYTHON_EXECUTABLE,
                "default_model_available": default_model_available,
            },
            "resources": settings.resource_summary(),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="Video Processing Workbench CLI",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    process_parser = subcommands.add_parser("process", help="Run the processing pipeline")
    process_parser.add_argument("--input", required=True, help="Input video path")
    process_parser.add_argument("--output", default=None, help="Optional output file path")
    process_parser.add_argument(
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
    process_parser.add_argument("--enable-interpolation", action="store_true", help="Enable interpolation stage")
    process_parser.add_argument("--enable-super-resolution", action="store_true", help="Enable super-resolution stage")
    process_parser.add_argument(
        "--process-order",
        default="super_resolution_then_interpolation",
        choices=list(PROCESS_ORDER_MAP.keys()),
        help="Stage order when interpolation and super-resolution are both enabled",
    )
    process_parser.add_argument("--fps", type=float, default=60.0, help="Default output FPS")
    process_parser.add_argument("--fps-mode", default="multi", choices=["multi", "target"], help="FPS calculation mode")
    process_parser.add_argument("--target-fps", type=float, default=60.0, help="Target FPS when using target mode")
    process_parser.add_argument("--codec", default="libx264", help="Video codec")
    process_parser.add_argument("--crf", type=int, default=18, help="CRF quality")
    process_parser.add_argument("--preset", default="medium", help="Encoding preset")
    process_parser.add_argument("--backend", default="pytorch", choices=["pytorch", "paddle"], help="Tensor backend")
    process_parser.add_argument("--output-dir", default=None, help="Output directory override")
    process_parser.add_argument("--multi", type=int, default=2, help="Interpolation multiplier")
    process_parser.add_argument("--model", default="4.25", help="RIFE model version")
    process_parser.add_argument("--scale", type=float, default=1.0, help="Interpolation scale factor")
    process_parser.add_argument("--fp16", action="store_true", help="Enable FP16 inference")
    process_parser.add_argument("--sr-scale-factor", type=float, default=2.0, help="Super-resolution scale")
    process_parser.add_argument("--sr-algorithm", default="placeholder", help="Super-resolution algorithm")
    process_parser.add_argument("--decode-config-json", default=None, help="Nested decode config JSON")
    process_parser.add_argument("--encode-config-json", default=None, help="Nested encode config JSON")
    process_parser.add_argument("--workflow-config-json", default=None, help="Nested workflow config JSON")
    process_parser.add_argument("--output-config-json", default=None, help="Nested output config JSON")
    process_parser.set_defaults(func=cmd_process)

    info_parser = subcommands.add_parser("info", help="Inspect an input video")
    info_parser.add_argument("--input", required=True, help="Input video path")
    info_parser.set_defaults(func=cmd_info)

    check_parser = subcommands.add_parser("check", help="Inspect runtime availability")
    check_parser.set_defaults(func=cmd_check)

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        _emit_error("cancelled", "Operation cancelled by the user.", exit_code=130)


if __name__ == "__main__":
    main()
