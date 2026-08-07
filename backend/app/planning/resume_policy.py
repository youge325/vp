"""Pure output-conflict and resume policy."""

from __future__ import annotations

from typing import Literal

from app.generated.contracts import ResumeMode

_OutputAction = Literal["conflict", "fresh", "resume"]


def decide_output_action(
    *,
    final_exists: bool,
    sidecar_exists: bool,
    signature_match: bool,
    has_progress: bool,
    mode: ResumeMode,
) -> _OutputAction:
    if final_exists and mode == ResumeMode.AUTO:
        return "conflict"
    if mode == ResumeMode.FORCE_FRESH:
        return "fresh"
    if not sidecar_exists or not signature_match:
        return "fresh"
    return "resume" if has_progress else "fresh"
