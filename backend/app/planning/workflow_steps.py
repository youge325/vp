"""Workflow config to processing-step planning helpers.

This module is the planning-layer source of truth for stage ordering,
algorithm kwargs, stage names, and output-frame estimates. CLI modules may
build default config dictionaries, but they should not own resolved stage
planning rules.
"""

from __future__ import annotations

import math
from typing import Any

from app.config import settings
from app.planning.processing_steps import AlgorithmType, ProcessingStep
from app.utils.ffmpeg import FFmpegWrapper

PROCESS_ORDER_MAP: dict[str, list[AlgorithmType]] = {
    "super_resolution_then_interpolation": [
        "super_resolution",
        "frame_interpolation",
    ],
    "frame_interpolation_then_super_resolution": [
        "frame_interpolation",
        "super_resolution",
    ],
}


def processing_needs_interpolation(processing_steps: list[ProcessingStep]) -> bool:
    return any(step.algorithm_type == "frame_interpolation" for step in processing_steps)


def resolve_primary_algorithm(workflow_config: dict[str, Any]) -> AlgorithmType:
    if workflow_config["interpolation"]["enabled"]:
        return "frame_interpolation"
    if workflow_config["superResolution"]["enabled"]:
        return "super_resolution"
    return "format_conversion"


def _build_algorithm_kwargs(workflow_config: dict[str, Any], algorithm_type: AlgorithmType) -> dict[str, Any]:
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
            "tensor_backend": super_resolution.get("tensorBackend")
            or super_resolution.get("tensor_backend")
            or interpolation.get("tensorBackend")
            or interpolation.get("tensor_backend"),
            "num_frames": super_resolution.get("numFrames") or super_resolution.get("num_frames"),
        }
    if algorithm_type == "frame_filter_chain":
        return {}
    return {}


def _resolve_algorithm_types(workflow_config: dict[str, Any], algorithm: AlgorithmType) -> list[AlgorithmType]:
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


def _compose_filter_chain(workflow_config: dict[str, Any], kind: str, existing_count: int) -> ProcessingStep | None:
    section = workflow_config.get(kind, {})
    if not section.get("enabled"):
        return None
    return ProcessingStep(
        algorithm_type="frame_filter_chain",
        algorithm_kwargs={"filters": section["filters"]},
        stage_name=f"{existing_count + 1:02d}_{kind}",
    )


def resolve_processing_steps(
    workflow_config: dict[str, Any], algorithm: AlgorithmType | None = None
) -> list[ProcessingStep]:
    algorithm_types = _resolve_algorithm_types(workflow_config, algorithm or resolve_primary_algorithm(workflow_config))
    steps: list[ProcessingStep] = []

    preprocess = _compose_filter_chain(workflow_config, "preprocess", len(steps))
    if preprocess is not None:
        steps.append(preprocess)

    for algorithm_type in algorithm_types:
        steps.append(
            ProcessingStep(
                algorithm_type=algorithm_type,
                algorithm_kwargs=_build_algorithm_kwargs(workflow_config, algorithm_type),
                stage_name=f"{len(steps) + 1:02d}_{algorithm_type}",
            )
        )

    postprocess = _compose_filter_chain(workflow_config, "postprocess", len(steps))
    if postprocess is not None:
        steps.append(postprocess)

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


def resolve_workflow_and_output_fps(
    workflow_config: dict[str, Any],
    ffmpeg: FFmpegWrapper,
    input_path: str,
) -> tuple[dict[str, Any], float | None]:
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


def resolve_expected_output_frames(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    workflow_config: dict[str, Any],
    processing_steps: list[ProcessingStep],
    final_output_fps: float | None,
) -> int:
    source_frames = ffmpeg.get_frame_count(input_path)
    if source_frames <= 0:
        return 1
    if final_output_fps is not None:
        duration = ffmpeg.get_duration(input_path)
        if duration > 0:
            return max(1, int(round(duration * final_output_fps)))
    if not processing_needs_interpolation(processing_steps):
        return source_frames

    multi = int(workflow_config["interpolation"].get("multi") or settings.RIFE_DEFAULT_MULTI)
    if source_frames < 2:
        return source_frames
    return source_frames + (source_frames - 1) * (multi - 1)
