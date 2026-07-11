"""``python -m app inspect-output`` handler.

Pure read-only pre-flight probe.  Returns a JSON payload describing
whether the planned final output and resume sidecar already exist, and
how much progress the sidecar represents.  Called by the Tauri host
before spawning ``process``.

Phase 16 — 改走 ``load_runtime_configs(args)`` 替代原本的 8 行
try/except + 4 个重复 JSON 解析块。``load_runtime_configs`` 是
``_process_validation`` 的 SSOT,inspect_output 历史遗留没接进来,导致两份
等价代码并存(添加字段时必须同时改两处,容易漂移)。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.cli.commands._process_validation import (
    ensure_input_and_ffmpeg,
    load_runtime_configs,
)
from app.planning import (
    SegmentManifest,
    build_signature,
    build_stage_plan,
    resolve_processing_steps,
    resolve_video_info,
    resolve_workflow_and_output_fps,
)
from app.protocol import ndjson
from app.utils.file_utils import get_output_path


def cmd_inspect_output(args: argparse.Namespace) -> None:
    input_path = args.input
    ffmpeg = ensure_input_and_ffmpeg(input_path)

    configs = load_runtime_configs(args)
    workflow_config = configs.workflow_json

    processing_steps = resolve_processing_steps(workflow_config)

    # Phase 18 — Pydantic ``OutputConfig`` validator 保证 outputDir 必填非空,
    # 这里不再 ``or settings.OUTPUT_DIR`` 兜底。
    output_dir = configs.output.output_dir
    container = configs.encode.container or "mp4"
    if args.output:
        output_path = args.output
    else:
        output_path = get_output_path(input_path, output_dir, extension=f".{container}")

    workflow_config, final_output_fps = resolve_workflow_and_output_fps(
        workflow_config,
        ffmpeg,
        input_path,
    )
    configs = configs.with_workflow_json(workflow_config)

    video_info = resolve_video_info(ffmpeg, input_path)
    stage_plan = build_stage_plan(
        processing_steps,
        video_info["source_frames"],
        source_duration=video_info["duration"],
        output_fps=final_output_fps,
    )

    if processing_steps:
        sections = configs.legacy_sections()
        signature = build_signature(
            input_path=input_path,
            output_path=output_path,
            decode_config=sections["decode"],
            encode_config=sections["encode"],
            workflow_config=sections["workflow"],
            output_config=sections["output"],
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
