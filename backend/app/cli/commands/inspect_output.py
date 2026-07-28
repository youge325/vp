"""``python -m app inspect-output`` handler.

Pure read-only preflight probe. Returns a JSON payload describing
whether the planned final output and resume sidecar already exist, and
how much progress the sidecar represents.  Called by the Tauri host
before spawning ``process``.

Configuration validation and preflight construction are shared with the
``process`` command.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.cli.commands._guards import ensure_input_and_ffmpeg
from app.cli.commands._pipeline_preparation import prepare_pipeline_preflight
from app.cli.commands._process_validation import load_runtime_configs
from app.planning import SegmentManifest
from app.protocol import ndjson
from app.utils.file_utils import prepare_default_output_path


def cmd_inspect_output(args: argparse.Namespace) -> None:
    input_path = args.input
    ffmpeg = ensure_input_and_ffmpeg(input_path)

    configs = load_runtime_configs(args)
    # Pydantic ``OutputConfig`` guarantees a non-empty outputDir.
    output_dir = configs.output.output_dir
    container = configs.encode.container or "mp4"
    if args.output:
        output_path = args.output
    else:
        output_path = prepare_default_output_path(input_path, output_dir, container)

    pipeline = prepare_pipeline_preflight(
        ffmpeg=ffmpeg,
        input_path=input_path,
        output_path=output_path,
        configs=configs,
    )
    processing_steps = pipeline.processing_steps
    preflight = pipeline.preflight

    if processing_steps:
        manifest = SegmentManifest(output_path)
        info = manifest.inspect(
            preflight.signature,
            total_output_frames=preflight.stage_plan.total_encoded_frames,
        )
    else:
        # Format conversion path has no sidecar; only the final-file check matters.
        resolved_output = Path(output_path).expanduser().resolve()
        info = {
            "outputPath": str(resolved_output),
            "finalExists": resolved_output.exists(),
            "sidecarExists": False,
            "signatureMatch": False,
            "completedChunks": 0,
            "completedOutputFrames": 0,
            "nextSourceFrame": 0,
            "totalOutputFrames": preflight.stage_plan.total_encoded_frames,
        }

    info["input_path"] = input_path
    info["pipeline_kind"] = "streaming" if processing_steps else "format_conversion"
    ndjson.resume_inspection(**info)
