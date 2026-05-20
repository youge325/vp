"""``python -m app inspect-output`` handler.

Pure read-only pre-flight probe.  Returns a JSON payload describing
whether the planned final output and resume sidecar already exist, and
how much progress the sidecar represents.  Called by the Tauri host
before spawning ``process``.

Phase 16 — 改走 ``load_configs(args)`` 替代原本的 8 行 try/except + 4 个
``_load_json_arg`` 重复块。``load_configs`` 是 ``_process_validation`` 的
SSOT,inspect_output 历史遗留没接进来,导致两份等价代码并存(添加字段
时必须同时改两处,容易漂移)。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.cli.commands._process_validation import (
    ensure_input_and_ffmpeg,
    load_configs,
)
from app.cli.defaults import (
    _resolve_processing_steps,
    _resolve_workflow_and_output_fps,
)
from app.config import settings
from app.planning import (
    SegmentManifest,
    build_signature,
    build_stage_plan,
    resolve_video_info,
)
from app.protocol import ndjson
from app.utils.file_utils import get_output_path


def cmd_inspect_output(args: argparse.Namespace) -> None:
    input_path = args.input
    ffmpeg = ensure_input_and_ffmpeg(input_path)

    decode_config, encode_config, workflow_config, output_config = load_configs(args)

    processing_steps = _resolve_processing_steps(workflow_config)

    output_dir = output_config.get("outputDir") or settings.OUTPUT_DIR
    container = str(encode_config.get("container") or "mp4")
    if args.output:
        output_path = args.output
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")

    workflow_config, final_output_fps = _resolve_workflow_and_output_fps(
        workflow_config,
        ffmpeg,
        input_path,
    )

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
