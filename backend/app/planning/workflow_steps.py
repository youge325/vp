"""Classify the primary user-facing operation for CLI reporting."""

from __future__ import annotations

from typing import Any, Literal

from app.planning.processing_steps import AlgorithmType

PrimaryAlgorithm = AlgorithmType | Literal["format_conversion"]


def resolve_primary_algorithm(workflow_config: dict[str, Any]) -> PrimaryAlgorithm:
    if workflow_config["interpolation"]["enabled"]:
        return "frame_interpolation"
    if workflow_config["superResolution"]["enabled"]:
        return "super_resolution"
    return "format_conversion"
