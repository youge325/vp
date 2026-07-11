"""Default config factories for CLI fallback payloads.

Pure functions called by both the ``process`` and ``inspect-output``
subcommands when no explicit nested config JSON is provided.
"""

from __future__ import annotations

import argparse
from typing import Any

from app.config import settings


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
            "tensorBackend": "onnx",
            "engine": "cuda",
            "numFrames": 10,
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
