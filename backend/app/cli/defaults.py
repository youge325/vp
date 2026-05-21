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
    multi = args.multi if args.multi is not None else settings.RIFE_DEFAULT_MULTI
    model = args.model if args.model is not None else settings.RIFE_MODEL_VERSION
    scale = args.scale if args.scale is not None else settings.RIFE_SCALE
    fp16 = args.fp16 if args.fp16 is not None else settings.RIFE_FP16
    return {
        "fpsMode": args.fps_mode,
        "processOrder": args.process_order,
        "interpolation": {
            "enabled": enable_interpolation,
            "targetFps": args.target_fps,
            "multi": multi,
            "model": model,
            "onnxModel": "",
            "scale": scale,
            "fp16": fp16,
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
    # Phase 18 — outputDir 强制必填,无 settings 兜底。
    # 这里允许返回空串是为了"defaults 与 partial payload 合并"路径(merge
    # 后 Pydantic ``OutputConfig`` validator 会拒空,fail-loudly)。直接
    # CLI 调用如果没传 ``--output-dir`` 也会经过 validator 报 INVALID_CONFIG,
    # 上层捕捉后返回结构化错误。
    return {
        "outputDir": args.output_dir or "",
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


def _resolve_algorithm_types(workflow_config: dict[str, Any], algorithm: str) -> list[str]:
    enable_interpolation = bool(workflow_config["interpolation"]["enabled"])
    enable_super_resolution = bool(workflow_config["superResolution"]["enabled"])

    if enable_interpolation and enable_super_resolution:
        return PROCESS_ORDER_MAP[workflow_config["processOrder"]]
    if enable_interpolation:
        return ["frame_interpolation"]
    if enable_super_resolution:
        return ["super_resolution"]
    if algorithm == "format_conversion":
        return []
    return [algorithm]


def _compose_filter_chain(workflow_config: dict[str, Any], kind: str, existing_count: int) -> dict[str, Any] | None:
    section = workflow_config.get(kind, {})
    if not section.get("enabled"):
        return None
    return {
        "algorithm_type": "frame_filter_chain",
        "algorithm_kwargs": {"filters": section["filters"]},
        "stage_name": f"{existing_count + 1:02d}_{kind}",
    }


def _steps_from_workflow(workflow_config: dict[str, Any], algorithm: str) -> list[dict[str, Any]]:
    algorithm_types = _resolve_algorithm_types(workflow_config, algorithm)
    steps: list[dict[str, Any]] = []

    preprocess = _compose_filter_chain(workflow_config, "preprocess", len(steps))
    if preprocess is not None:
        steps.append(preprocess)

    for algorithm_type in algorithm_types:
        steps.append(
            {
                "algorithm_type": algorithm_type,
                "algorithm_kwargs": _build_algorithm_kwargs(workflow_config, algorithm_type),
                "stage_name": f"{len(steps) + 1:02d}_{algorithm_type}",
            }
        )

    postprocess = _compose_filter_chain(workflow_config, "postprocess", len(steps))
    if postprocess is not None:
        steps.append(postprocess)

    return steps


def _resolve_processing_steps(config_or_args: dict[str, Any] | argparse.Namespace) -> list[dict[str, Any]]:
    if isinstance(config_or_args, argparse.Namespace):
        workflow_config = _default_workflow_config(config_or_args)
        algorithm = config_or_args.algorithm
    else:
        workflow_config = config_or_args
        algorithm = _resolve_primary_algorithm(workflow_config)
    return _steps_from_workflow(workflow_config, algorithm)


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


def _resolve_workflow_and_output_fps(
    workflow_config: dict[str, Any],
    ffmpeg: FFmpegWrapper,
    input_path: str,
) -> tuple[dict[str, Any], float | None]:
    """Phase D.6.3 — 把 _resolve_fps_and_multi 的两段样板收敛到一处。

    `_process_planning.build_plan` 与 `cmd_inspect_output` 都需要:
    1. 调 `_resolve_fps_and_multi` 拿到推导后的 multi / encode_fps / need_resample
    2. 用不 mutate 原对象的方式把 multi 写回 workflow_config
    3. 把 encode_fps 折算为 `final_output_fps`(仅当 need_resample 时使用)

    返回的 ``workflow_config`` 是一个新对象;调用方应整体替换变量绑定,
    不要继续使用旧的引用。
    """
    multi, encode_fps, _interpolated_fps, need_resample = _resolve_fps_and_multi(
        workflow_config,
        ffmpeg,
        input_path,
    )
    new_workflow_config = {
        **workflow_config,
        "interpolation": {**workflow_config["interpolation"], "multi": multi},
    }
    final_output_fps = encode_fps if need_resample else None
    return new_workflow_config, final_output_fps


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
