"""Canonical stage ordering and timeline projection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, assert_never

from app.planning.processing_steps import ProcessingStep
from app.ports.media import VideoMetadata

type StageAlgorithmType = Literal["frame_interpolation", "super_resolution"]

_PROCESS_ORDER_MAP: dict[str, tuple[StageAlgorithmType, ...]] = {
    "super_resolution_then_interpolation": (
        "super_resolution",
        "frame_interpolation",
    ),
    "frame_interpolation_then_super_resolution": (
        "frame_interpolation",
        "super_resolution",
    ),
}


@dataclass(frozen=True, slots=True)
class ProjectedStage:
    """One stage's position and projected input/output timeline."""

    position: int
    step: ProcessingStep
    input_frames: int
    output_frames: int
    output_fps: float
    input_width: int
    input_height: int
    output_width: int
    output_height: int


@dataclass(frozen=True, slots=True)
class StageProjection:
    """The sole owner of stage order, frame-count, and FPS projection."""

    steps: tuple[ProcessingStep, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))

    @classmethod
    def from_workflow(cls, workflow_config: dict[str, Any]) -> StageProjection:
        """Resolve configured stages in their canonical execution order."""
        algorithm_types = cls._algorithm_types(workflow_config)
        steps: list[ProcessingStep] = []

        preprocess = cls._filter_chain(workflow_config, "preprocess", len(steps))
        if preprocess is not None:
            steps.append(preprocess)

        for algorithm_type in algorithm_types:
            steps.append(
                ProcessingStep(
                    algorithm_type=algorithm_type,
                    algorithm_kwargs=cls._algorithm_kwargs(workflow_config, algorithm_type),
                    stage_name=f"{len(steps) + 1:02d}_{algorithm_type}",
                )
            )

        postprocess = cls._filter_chain(workflow_config, "postprocess", len(steps))
        if postprocess is not None:
            steps.append(postprocess)
        return cls(tuple(steps))

    @classmethod
    def resolve_workflow(
        cls,
        workflow_config: dict[str, Any],
        *,
        source_fps: float,
    ) -> tuple[dict[str, Any], StageProjection, float | None]:
        """Resolve interpolation multiplicity, stage order, and encoder FPS."""
        interpolation = workflow_config["interpolation"]
        fps_mode = workflow_config["fpsMode"]
        if fps_mode == "target":
            target_fps = float(interpolation["targetFps"])
            multi = max(2, math.ceil(target_fps / source_fps))
        else:
            multi = int(interpolation["multi"])

        resolved_workflow = {
            **workflow_config,
            "interpolation": {**interpolation, "multi": multi},
        }
        projection = cls.from_workflow(resolved_workflow)
        target_fps = float(interpolation["targetFps"]) if fps_mode == "target" else None
        return resolved_workflow, projection, target_fps

    def stages(
        self,
        source: VideoMetadata,
    ) -> tuple[ProjectedStage, ...]:
        """Materialize every ordered stage for one canonical source."""
        current_frames = int(source.source_frames)
        current_fps = float(source.source_fps)
        current_width = int(source.width)
        current_height = int(source.height)
        projected: list[ProjectedStage] = []
        for position, step in enumerate(self.steps, start=1):
            output_frames = self.project_frame_count(step, current_frames)
            output_fps = self.project_fps(step, current_fps)
            output_width, output_height = step.descriptor.geometry.project(
                input_width=current_width,
                input_height=current_height,
                algorithm_kwargs=step.algorithm_kwargs,
            )
            projected.append(
                ProjectedStage(
                    position=position,
                    step=step,
                    input_frames=current_frames,
                    output_frames=output_frames,
                    output_fps=output_fps,
                    input_width=current_width,
                    input_height=current_height,
                    output_width=output_width,
                    output_height=output_height,
                )
            )
            current_frames = output_frames
            current_fps = output_fps
            current_width = output_width
            current_height = output_height
        return tuple(projected)

    @staticmethod
    def project_frame_count(step: ProcessingStep, input_frame_count: int) -> int:
        if step.algorithm_type != "frame_interpolation" or input_frame_count < 2:
            return input_frame_count
        return StageProjection.interpolation_output_frame_count(
            input_frame_count,
            int(step.algorithm_kwargs["multi"]),
        )

    @staticmethod
    def interpolation_output_frame_count(input_frame_count: int, multi: int) -> int:
        if input_frame_count < 2:
            return input_frame_count
        return input_frame_count + (input_frame_count - 1) * (multi - 1)

    @staticmethod
    def project_fps(step: ProcessingStep, input_fps: float) -> float:
        if step.algorithm_type != "frame_interpolation":
            return input_fps
        return input_fps * int(step.algorithm_kwargs["multi"])

    @staticmethod
    def _algorithm_types(workflow_config: dict[str, Any]) -> tuple[StageAlgorithmType, ...]:
        interpolation_enabled = bool(workflow_config["interpolation"]["enabled"])
        super_resolution_enabled = bool(workflow_config["superResolution"]["enabled"])
        if interpolation_enabled and super_resolution_enabled:
            return _PROCESS_ORDER_MAP[workflow_config["processOrder"]]
        if interpolation_enabled:
            return ("frame_interpolation",)
        if super_resolution_enabled:
            return ("super_resolution",)
        return ()

    @staticmethod
    def _algorithm_kwargs(workflow_config: dict[str, Any], algorithm_type: StageAlgorithmType) -> dict[str, Any]:
        interpolation = workflow_config["interpolation"]
        super_resolution = workflow_config["superResolution"]
        if algorithm_type == "frame_interpolation":
            return {
                "multi": interpolation["multi"],
                "algorithm": interpolation["algorithm"],
                "model_version": interpolation["model"],
                "scale": interpolation["scale"],
                "fp16": interpolation["fp16"],
                "onnx_model": interpolation.get("onnxModel"),
                "engine": interpolation["engine"],
                "tensor_backend": interpolation["tensorBackend"],
            }
        if algorithm_type == "super_resolution":
            return {
                "scale_factor": super_resolution["scaleFactor"],
                "sr_algorithm": super_resolution["algorithm"],
                "onnx_model": super_resolution.get("onnxModel"),
                "engine": super_resolution["engine"],
                "tensor_backend": super_resolution["tensorBackend"],
                "num_frames": super_resolution["numFrames"],
            }
        assert_never(algorithm_type)

    @staticmethod
    def _filter_chain(
        workflow_config: dict[str, Any],
        kind: str,
        existing_count: int,
    ) -> ProcessingStep | None:
        section = workflow_config.get(kind, {})
        filters = section.get("filters", ())
        if not section.get("enabled") or not any(filter_step.get("enabled", True) for filter_step in filters):
            return None
        return ProcessingStep(
            algorithm_type="frame_filter_chain",
            algorithm_kwargs={"filters": filters},
            stage_name=f"{existing_count + 1:02d}_{kind}",
        )


__all__ = ["StageProjection"]
