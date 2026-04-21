"""CLI entry point for ``python -m app check|info|process``."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.algorithms.factory import register_default_algorithms
from app.config import settings
from app.processing.decoder import DecodeFilter
from app.processing.encoder import EncodeFilter
from app.processing.frame_processor import FrameProcessFilter
from app.processing.pipeline import Pipeline
from app.utils.ffmpeg_wrapper import FFmpegWrapper
from app.utils.file_utils import cleanup_dir, get_output_path, validate_input_path
from app.utils.logger import get_logger, setup_logging

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
    "frame_interpolation": "Video Interpolation",
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


def _build_algorithm_kwargs(args: argparse.Namespace, algorithm_type: str) -> dict[str, Any]:
    if algorithm_type == "frame_interpolation":
        return {
            "multi": args.multi,
            "model_version": args.model,
            "scale": args.scale,
            "fp16": args.fp16,
        }
    if algorithm_type == "super_resolution":
        return {
            "scale_factor": args.sr_scale_factor,
            "sr_algorithm": args.sr_algorithm,
        }
    return {}


def _resolve_processing_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    enable_interpolation = bool(args.enable_interpolation)
    enable_super_resolution = bool(args.enable_super_resolution)

    if enable_interpolation or enable_super_resolution:
        if enable_interpolation and enable_super_resolution:
            algorithm_types = PROCESS_ORDER_MAP[args.process_order]
        elif enable_interpolation:
            algorithm_types = ["frame_interpolation"]
        else:
            algorithm_types = ["super_resolution"]
    elif args.algorithm == "format_conversion":
        algorithm_types = []
    else:
        algorithm_types = [args.algorithm]

    steps: list[dict[str, Any]] = []
    for index, algorithm_type in enumerate(algorithm_types, start=1):
        steps.append(
            {
                "algorithm_type": algorithm_type,
                "algorithm_kwargs": _build_algorithm_kwargs(args, algorithm_type),
                "stage_name": f"{index:02d}_{algorithm_type}",
            }
        )
    return steps


def _make_progress_callback(stage_index: int, total_stages: int, algorithm_type: str):
    def progress_callback(current: int, total: int) -> None:
        stage_fraction = (current / total) if total > 0 else 0.0
        if total_stages > 0:
            overall_percent = ((stage_index + stage_fraction) / total_stages) * 100
        else:
            overall_percent = stage_fraction * 100

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
    args: argparse.Namespace,
    ffmpeg: FFmpegWrapper,
    input_path: str,
) -> tuple[int, float, float | None, bool]:
    fps_mode = getattr(args, "fps_mode", "multi")

    if fps_mode == "target":
        target_fps = getattr(args, "target_fps", 60.0)
        source_fps = ffmpeg.get_fps(input_path)
        multi = max(2, math.ceil(target_fps / source_fps))
        interpolated_fps = source_fps * multi
        need_resample = interpolated_fps > target_fps
        encode_fps = target_fps if need_resample else interpolated_fps
        return multi, encode_fps, interpolated_fps, need_resample

    return args.multi, args.fps, None, False


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

    processing_steps = _resolve_processing_steps(args)
    if _processing_needs_interpolation(processing_steps):
        model_path = _model_path(args.model)
        if not model_path.is_file() or model_path.stat().st_size == 0:
            _emit_error(
                "missing_model",
                f"Default interpolation model is missing: {model_path}",
                details={
                    "model_path": str(model_path),
                    "model_version": args.model,
                },
            )

    output_dir = args.output_dir or settings.OUTPUT_DIR
    temp_dir = args.temp_dir or settings.TEMP_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.RIFE_MODEL_DIR).mkdir(parents=True, exist_ok=True)

    if args.output:
        output_path = args.output
        Path(output_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_output_path(input_path, output_dir)

    multi, encode_fps, _interpolated_fps, need_resample = _resolve_fps_and_multi(args, ffmpeg, input_path)
    if getattr(args, "fps_mode", "multi") == "target":
        args.multi = multi

    pipeline = Pipeline(name=f"task_{uuid.uuid4().hex[:12]}")
    pipeline.add_filter(DecodeFilter(ffmpeg_wrapper=ffmpeg))
    for stage_index, step in enumerate(processing_steps):
        pipeline.add_filter(
            FrameProcessFilter(
                algorithm_type=step["algorithm_type"],
                tensor_backend_name=args.backend,
                progress_callback=_make_progress_callback(stage_index, len(processing_steps), step["algorithm_type"]),
                algorithm_kwargs=step["algorithm_kwargs"],
                stage_name=step["stage_name"],
            )
        )
    pipeline.add_filter(
        EncodeFilter(
            ffmpeg_wrapper=ffmpeg,
            codec=args.codec,
            crf=args.crf,
            preset=args.preset,
        )
    )

    input_data = {
        "input_path": input_path,
        "output_path": output_path,
        "fps": args.fps,
    }
    context: dict[str, Any] = {
        "task_id": uuid.uuid4().hex[:12],
        "temp_dir": temp_dir,
        "output_dir": output_dir,
        "processing_steps": processing_steps,
    }
    if need_resample:
        context["target_fps"] = encode_fps

    start_time = time.time()
    try:
        result = pipeline.execute(input_data, context)
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
            "cancelled", "Processing was cancelled by the user.", details={"input_path": input_path}, exit_code=130
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        _emit_error(
            _infer_error_code(exc),
            str(exc),
            details={
                "input_path": input_path,
                "output_path": output_path,
                "algorithm": args.algorithm,
                "processing_steps": [step["algorithm_type"] for step in processing_steps],
            },
        )
    finally:
        frame_dir = context.get("frame_dir")
        if frame_dir and os.path.isdir(frame_dir):
            cleanup_dir(os.path.dirname(frame_dir))


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

    default_model_path = _model_path()
    default_model_available = default_model_path.is_file() and default_model_path.stat().st_size > 0

    _emit(
        {
            "type": "check",
            "ffmpeg": {
                "available": ffmpeg_available,
                "path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
                "version": ffmpeg_version,
            },
            "gpu": {
                "available": pytorch_result["gpu_available"],
                "devices": pytorch_result["gpu_devices"],
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
    process_parser.add_argument(
        "--fps-mode",
        default="multi",
        choices=["multi", "target"],
        help="FPS calculation mode",
    )
    process_parser.add_argument("--target-fps", type=float, default=60.0, help="Target FPS when using target mode")
    process_parser.add_argument("--codec", default="libx264", help="Video codec")
    process_parser.add_argument("--crf", type=int, default=18, help="CRF quality")
    process_parser.add_argument("--preset", default="medium", help="Encoding preset")
    process_parser.add_argument(
        "--backend",
        default="pytorch",
        choices=["pytorch", "paddle"],
        help="Tensor backend",
    )
    process_parser.add_argument("--temp-dir", default=None, help="Temporary directory override")
    process_parser.add_argument("--output-dir", default=None, help="Output directory override")
    process_parser.add_argument("--multi", type=int, default=2, help="Interpolation multiplier")
    process_parser.add_argument("--model", default="4.25", help="RIFE model version")
    process_parser.add_argument("--scale", type=float, default=1.0, help="Interpolation scale factor")
    process_parser.add_argument("--fp16", action="store_true", help="Enable FP16 inference")
    process_parser.add_argument("--sr-scale-factor", type=float, default=2.0, help="Super-resolution scale")
    process_parser.add_argument("--sr-algorithm", default="placeholder", help="Super-resolution algorithm")
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
