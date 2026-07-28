"""Pure output-conflict and resume policy."""

from __future__ import annotations

from typing import Literal

ResumeMode = Literal["auto", "force-fresh", "force-resume"]
OutputAction = Literal["conflict", "fresh", "resume"]


def decide_output_action(
    *,
    final_exists: bool,
    sidecar_exists: bool,
    signature_match: bool,
    has_progress: bool,
    mode: ResumeMode,
) -> OutputAction:
    if final_exists and mode == "auto":
        return "conflict"
    if mode == "force-fresh":
        return "fresh"
    if not sidecar_exists or not signature_match:
        return "fresh"
    return "resume" if has_progress else "fresh"
