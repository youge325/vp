"""Default configs, planning maps, and stage-plan resolution.

Pure functions called by both the ``process`` and ``inspect-output``
subcommands.  Takes either an ``argparse.Namespace`` (for CLI fallback
defaults) or a fully validated workflow config dict.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from app.config import settings
from app.utils.ffmpeg import FFmpegWrapper

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
