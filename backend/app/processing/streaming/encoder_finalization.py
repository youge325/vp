"""Finalize segmented encoder output into the requested video file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.planning import SegmentManifest
from app.utils.ffmpeg import FFmpegWrapper


def finalize_segmented_output(
    *,
    ffmpeg: FFmpegWrapper,
    input_path: str,
    output_path: str,
    encode_config: dict[str, Any],
    manifest: SegmentManifest,
    completed_output_frames: int,
    total_output_frames: int,
    strict_total_frames: bool,
) -> None:
    completed_segments = manifest.scan_completed_chunks()
    segment_paths = [str(manifest.sidecar_dir / record.path) for record in completed_segments]
    if strict_total_frames and completed_output_frames != total_output_frames:
        raise RuntimeError(
            f"Temporary segments are incomplete: expected {total_output_frames} output frames, "
            f"got {completed_output_frames}."
        )
    if not segment_paths:
        raise RuntimeError("No completed temporary segments were found for finalization.")

    extension = os.path.splitext(output_path)[1] or f".{encode_config.get('container') or 'mp4'}"
    concat_path = manifest.concat_temp_path(extension)
    ffmpeg.concat_videos(segment_paths, concat_path)

    keep_audio = bool(encode_config.get("keepAudio", True))
    if keep_audio and ffmpeg.has_audio(input_path):
        audio_path = str(manifest.sidecar_dir / "source_audio.aac")
        if ffmpeg.extract_audio(input_path, audio_path):
            ffmpeg.merge_audio(concat_path, audio_path, output_path)
            Path(audio_path).unlink(missing_ok=True)
            Path(concat_path).unlink(missing_ok=True)
            return

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    os.replace(concat_path, output_path)


__all__ = ["finalize_segmented_output"]
