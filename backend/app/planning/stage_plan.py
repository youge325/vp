"""Materialized stage-plan derivation for the streaming pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_projection import ProjectedStage, StageProjection
from app.ports.media import MediaProbePort, VideoMetadata


@dataclass(frozen=True, slots=True)
class StagePlan:
    """One immutable projection shared by every execution path."""

    source: VideoMetadata
    stages: tuple[ProjectedStage, ...]
    encoder_fps_override: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))

    @property
    def processing_steps(self) -> tuple[ProcessingStep, ...]:
        return tuple(stage.step for stage in self.stages)

    @property
    def total_encoded_frames(self) -> int:
        processed_frames = self.stages[-1].output_frames if self.stages else self.source.source_frames
        if self.encoder_fps_override is None or self.source.duration <= 0:
            return processed_frames
        return max(1, int(round(self.source.duration * self.encoder_fps_override)))

    @property
    def interpolation_step(self) -> ProcessingStep | None:
        return next(
            (stage.step for stage in self.stages if stage.step.algorithm_type == "frame_interpolation"),
            None,
        )

    @property
    def requires_file_pipeline(self) -> bool:
        return any(stage.step.descriptor.requires_file_pipeline for stage in self.stages)

    @property
    def resume_source_frames(self) -> int:
        if self.requires_file_pipeline and self.stages:
            return self.stages[-1].input_frames
        return self.source.source_frames

    @property
    def output_dimensions(self) -> tuple[int, int]:
        if not self.stages:
            return self.source.width, self.source.height
        final = self.stages[-1]
        return final.output_width, final.output_height

    @property
    def stream_fps(self) -> float:
        if not self.stages:
            return self.source.source_fps
        return self.stages[-1].output_fps

    def slice_stages(self, source_frame_count: int) -> tuple[ProjectedStage, ...]:
        """Project only variable frame counts for a resumed source slice.

        Stage order, geometry and FPS remain those materialized during preflight.
        """
        current_frames = max(int(source_frame_count), 0)
        projected: list[ProjectedStage] = []
        for stage in self.stages:
            output_frames = StageProjection.project_frame_count(stage.step, current_frames)
            projected.append(replace(stage, input_frames=current_frames, output_frames=output_frames))
            current_frames = output_frames
        return tuple(projected)


def resolve_video_info(ffmpeg: MediaProbePort, input_path: str) -> VideoMetadata:
    """Probe a video and return canonical dimension / fps / frame-count metadata."""
    video_info = ffmpeg.probe_video(input_path)
    if video_info.width <= 0 or video_info.height <= 0:
        raise RuntimeError(f"Unable to resolve video dimensions for {input_path}")
    if video_info.source_fps <= 0:
        raise RuntimeError(f"Unable to resolve source FPS for {input_path}")
    if video_info.source_frames <= 0:
        raise RuntimeError(f"Unable to resolve source frame count for {input_path}")
    return video_info


def build_stage_plan(
    projection: StageProjection,
    source: VideoMetadata,
    *,
    output_fps: float | None,
) -> StagePlan:
    """Materialize the canonical projection exactly once for a probed video."""
    stages = projection.stages(source)
    projected_fps = stages[-1].output_fps if stages else source.source_fps
    encoder_fps_override = output_fps if output_fps is not None and projected_fps > output_fps else None
    return StagePlan(source=source, stages=stages, encoder_fps_override=encoder_fps_override)


__all__ = ["StagePlan", "build_stage_plan", "resolve_video_info"]
