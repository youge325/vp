"""Immutable result returned by every processing execution path."""

from dataclasses import dataclass

from app.ports.media import FrameCountProbePort


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    output_path: str
    processed_frames: int


def resolve_final_output_frame_count(
    probe: FrameCountProbePort,
    output_path: str,
    *,
    fallback: int,
) -> int:
    """Resolve terminal accounting without turning a completed output into an error."""
    try:
        frame_count = int(probe.get_frame_count(output_path) or 0)
    except Exception:
        frame_count = 0
    return frame_count if frame_count > 0 else max(int(fallback), 0)


__all__ = ["ExecutionResult", "resolve_final_output_frame_count"]
