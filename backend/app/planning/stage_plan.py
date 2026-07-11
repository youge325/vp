"""Stage plan + signature derivation for the streaming pipeline.

Pure functions: probe a video, build a deterministic SHA-256 signature
from the request, derive the ``StagePlan`` (pre/interp/post split +
frame counts) that the streaming workers consume.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from app.planning.processing_steps import (
    ProcessingStep,
)
from app.utils.ffmpeg import FFmpegWrapper


@dataclass(slots=True)
class StagePlan:
    """Resolved processing layout for the streaming executor."""

    pre_steps: list[ProcessingStep]
    interpolation_step: ProcessingStep | None
    post_steps: list[ProcessingStep]
    total_encoded_frames: int


def resolve_video_info(ffmpeg: FFmpegWrapper, input_path: str) -> dict[str, Any]:
    """Probe a video and return canonical dimension / fps / frame-count metadata."""
    info = ffmpeg.get_video_info(input_path)
    width = 0
    height = 0
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            break

    if width <= 0 or height <= 0:
        raise RuntimeError(f"Unable to resolve video dimensions for {input_path}")

    source_fps = ffmpeg.get_fps(input_path)
    source_frames = ffmpeg.get_frame_count(input_path)
    if source_frames <= 0:
        raise RuntimeError(f"Unable to resolve source frame count for {input_path}")

    return {
        "width": width,
        "height": height,
        "source_fps": source_fps,
        "source_frames": source_frames,
        "duration": ffmpeg.get_duration(input_path),
        "has_audio": ffmpeg.has_audio(input_path),
    }


def _estimate_encoded_output_frames(
    *,
    source_frames: int,
    source_duration: float,
    output_fps: float | None,
) -> int:
    """Estimate how many frames will be written by the encoder."""
    if output_fps is None:
        return source_frames
    if source_duration <= 0:
        return source_frames
    return max(1, int(round(source_duration * output_fps)))


def build_stage_plan(
    processing_steps: list[ProcessingStep],
    source_frames: int,
    *,
    source_duration: float,
    output_fps: float | None,
) -> StagePlan:
    """Derive a ``StagePlan`` from the requested pipeline steps and source metadata."""
    steps = list(processing_steps)
    interpolation_index = None
    for index, step in enumerate(steps):
        if step.algorithm_type == "frame_interpolation":
            interpolation_index = index
            break

    if interpolation_index is None:
        total_encoded_frames = _estimate_encoded_output_frames(
            source_frames=source_frames,
            source_duration=source_duration,
            output_fps=output_fps,
        )
        return StagePlan(
            pre_steps=steps,
            interpolation_step=None,
            post_steps=[],
            total_encoded_frames=total_encoded_frames,
        )

    interpolation_step = steps[interpolation_index]
    multi = int(interpolation_step.algorithm_kwargs.get("multi") or 2)
    if source_frames < 2:
        processed_output_frames = source_frames
    else:
        processed_output_frames = source_frames + (source_frames - 1) * (multi - 1)
    total_encoded_frames = _estimate_encoded_output_frames(
        source_frames=processed_output_frames,
        source_duration=source_duration,
        output_fps=output_fps,
    )

    return StagePlan(
        pre_steps=steps[:interpolation_index],
        interpolation_step=interpolation_step,
        post_steps=steps[interpolation_index + 1 :],
        total_encoded_frames=total_encoded_frames,
    )


def build_signature(
    *,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: list[ProcessingStep],
    video_info: dict[str, Any],
) -> str:
    """Return a deterministic SHA-256 signature for the processing configuration."""
    stat = os.stat(input_path)
    payload = {
        "input_path": os.path.abspath(input_path),
        "output_path": os.path.abspath(output_path),
        "input_size": stat.st_size,
        "input_mtime_ns": stat.st_mtime_ns,
        "decode_config": decode_config,
        "encode_config": encode_config,
        "workflow_config": workflow_config,
        "output_config": {
            "segmentFrames": max(1, int(output_config.get("segmentFrames") or 1000)),
        },
        "processing_steps": [step.to_jsonable() for step in processing_steps],
        "video_info": {
            "width": video_info["width"],
            "height": video_info["height"],
            "source_fps": video_info["source_fps"],
            "source_frames": video_info["source_frames"],
        },
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
