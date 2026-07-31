"""Stage-plan derivation for the streaming pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.planning.processing_steps import ProcessingStep
from app.planning.stage_projection import StageProjection
from app.ports.media import MediaProbePort, VideoMetadata


@dataclass(frozen=True, slots=True)
class StagePlan:
    """Resolved processing layout for the streaming executor."""

    projection: StageProjection = field(repr=False)
    source_frames: int
    source_duration: float
    output_fps: float | None
    steps: tuple[ProcessingStep, ...] = field(init=False)
    total_encoded_frames: int = field(init=False)
    interpolation_index: int | None = field(init=False)

    def __post_init__(self) -> None:
        steps = self.projection.steps
        object.__setattr__(self, "steps", steps)
        object.__setattr__(
            self,
            "total_encoded_frames",
            self.projection.encoded_output_frame_count(
                source_frames=self.source_frames,
                source_duration=self.source_duration,
                output_fps=self.output_fps,
            ),
        )
        object.__setattr__(
            self,
            "interpolation_index",
            next(
                (index for index, step in enumerate(steps) if step.algorithm_type == "frame_interpolation"),
                None,
            ),
        )

    @property
    def interpolation_step(self) -> ProcessingStep | None:
        index = self.interpolation_index
        return self.steps[index] if index is not None else None


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
    source_frames: int,
    *,
    source_duration: float,
    output_fps: float | None,
) -> StagePlan:
    """Derive a ``StagePlan`` from the canonical projection and source metadata."""
    return StagePlan(
        projection=projection,
        source_frames=source_frames,
        source_duration=source_duration,
        output_fps=output_fps,
    )


__all__ = [
    "StagePlan",
    "build_stage_plan",
    "resolve_video_info",
]
