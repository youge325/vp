"""``python -m app inspect-output`` handler.

Pure read-only pre-flight probe.  Returns a JSON payload describing
whether the planned final output and resume sidecar already exist, and
how much progress the sidecar represents.  Called by the Tauri host
before spawning ``process``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.cli.commands.process import _load_json_arg
from app.cli.defaults import (
    _default_decode_config,
    _default_encode_config,
    _default_output_config,
    _default_workflow_config,
    _resolve_fps_and_multi,
    _resolve_processing_steps,
)
from app.config import settings
from app.errors import TaskErrorCode, emit_error
from app.models import DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig
from app.planning import (
    SegmentManifest,
    build_signature,
    build_stage_plan,
    resolve_video_info,
)
from app.protocol import ndjson
from app.utils.ffmpeg import FFmpegWrapper
from app.utils.file_utils import get_output_path, validate_input_path


def cmd_inspect_output(args: argparse.Namespace) -> None:
    input_path = args.input
    if not validate_input_path(input_path):
        emit_error(
            TaskErrorCode.INVALID_INPUT,
            f"Input file is invalid or unsupported: {input_path}",
            details={"input_path": input_path},
        )

    ffmpeg = FFmpegWrapper()
    if not ffmpeg.is_available():
        emit_error(
            TaskErrorCode.MISSING_FFMPEG,
            "FFmpeg is not available.",
            details={
                "ffmpeg_path": ffmpeg.ffmpeg_path,
                "ffprobe_path": ffmpeg.ffprobe_path,
            },
        )

    try:
        decode_config = _load_json_arg(args.decode_config_json, _default_decode_config(), DecodeConfig)
        encode_config = _load_json_arg(args.encode_config_json, _default_encode_config(args), EncodeConfig)
        workflow_config = _load_json_arg(args.workflow_config_json, _default_workflow_config(args), WorkflowConfig)
        output_config = _load_json_arg(args.output_config_json, _default_output_config(args), OutputConfig)
    except ValueError as exc:
        emit_error(TaskErrorCode.INVALID_CONFIG, str(exc))

    processing_steps = _resolve_processing_steps(workflow_config)

    output_dir = output_config.get("outputDir") or settings.OUTPUT_DIR
    container = str(encode_config.get("container") or "mp4")
    if args.output:
        output_path = args.output
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")

    multi, encode_fps, _interpolated_fps, need_resample = _resolve_fps_and_multi(workflow_config, ffmpeg, input_path)
    workflow_config["interpolation"]["multi"] = multi
    final_output_fps = encode_fps if need_resample else None

    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        processing_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=final_output_fps,
    )

    if processing_steps:
        signature = build_signature(
            input_path=input_path,
            output_path=output_path,
            decode_config=decode_config,
            encode_config=encode_config,
            workflow_config=workflow_config,
            output_config=output_config,
            processing_steps=processing_steps,
            video_info=video_info,
        )
        manifest = SegmentManifest(output_path)
        info = manifest.inspect(
            signature,
            total_output_frames=stage_plan.total_encoded_frames,
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
            "totalOutputFrames": stage_plan.total_encoded_frames,
        }

    info["input_path"] = input_path
    info["pipeline_kind"] = "streaming" if processing_steps else "format_conversion"
    ndjson.resume_inspection(**info)
