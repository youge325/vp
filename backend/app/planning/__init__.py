"""Pipeline planning — pre-flight analysis and sidecar management.

Splits the original monolithic ``planning.py`` into two focused
sub-modules:

- ``stage_plan`` — pure signature / stage-plan / video-info helpers
- ``manifest`` — sidecar lifecycle and resume dataclasses
"""

from app.planning.manifest import (
    ResumeDecision,
    ResumeKind,
    ResumeMode,
    ResumeState,
    SegmentManifest,
    SegmentRecord,
)
from app.planning.stage_plan import (
    StagePlan,
    build_signature,
    build_stage_plan,
    estimate_encoded_output_frames,
    resolve_video_info,
)

__all__ = [
    "ResumeDecision",
    "ResumeKind",
    "ResumeMode",
    "ResumeState",
    "SegmentManifest",
    "SegmentRecord",
    "StagePlan",
    "build_signature",
    "build_stage_plan",
    "estimate_encoded_output_frames",
    "resolve_video_info",
]
