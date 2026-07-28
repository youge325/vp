"""Configuration snapshot and resume signature for one processing run."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Sequence

from app.planning.processing_steps import ProcessingStep
from app.ports.media import VideoMetadata


@dataclass(frozen=True, slots=True)
class _RunIdentity:
    """The persisted configuration snapshot and the signature derived from it."""

    signature: str
    config_snapshot: dict[str, Any]


def build_run_identity(
    *,
    input_path: str,
    output_path: str,
    decode_config: dict[str, Any],
    encode_config: dict[str, Any],
    workflow_config: dict[str, Any],
    output_config: dict[str, Any],
    processing_steps: Sequence[ProcessingStep],
    video_info: VideoMetadata,
) -> _RunIdentity:
    """Build the exact sidecar snapshot and its deterministic SHA-256 signature."""
    config_snapshot = deepcopy(
        {
            "input_path": os.path.abspath(input_path),
            "output_path": os.path.abspath(output_path),
            "decode_config": decode_config,
            "encode_config": encode_config,
            "workflow_config": workflow_config,
            "output_config": {
                "segmentFrames": int(output_config["segmentFrames"]),
            },
            "processing_steps": [step.to_jsonable() for step in processing_steps],
            "video_info": {
                "width": video_info.width,
                "height": video_info.height,
                "source_fps": video_info.source_fps,
                "source_frames": video_info.source_frames,
            },
        }
    )
    stat = os.stat(input_path)
    signature_payload = {
        **config_snapshot,
        "input_size": stat.st_size,
        "input_mtime_ns": stat.st_mtime_ns,
    }
    encoded = json.dumps(signature_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return _RunIdentity(
        signature=hashlib.sha256(encoded).hexdigest(),
        config_snapshot=config_snapshot,
    )


__all__ = ["build_run_identity"]
