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

from app.adapters.model_availability import LocalModelAvailability
from app.cli.commands._guards import ensure_input_and_ffmpeg
from app.cli.commands._pipeline_preparation import prepare_pipeline_preflight
from app.cli.commands._process_validation import load_runtime_configs
from app.config import settings
from app.generated.contracts import (
    ResumeInspectionEventType,
    ResumeInspectionResult,
    ResumePipelineKind,
)
from app.generated.protocol_constants import BackendEnvelopeType
from app.planning import ResumeInspection, SegmentManifest
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
        model_availability=LocalModelAvailability(settings.RIFE_MODEL_DIR),
    )
    processing_steps = pipeline.processing_steps
    preflight = pipeline.preflight

    if processing_steps:
        manifest = SegmentManifest(output_path)
        inspection = manifest.inspect(
            preflight.signature,
            total_output_frames=preflight.stage_plan.total_encoded_frames,
        )
    else:
        # Format conversion path has no sidecar; only the final-file check matters.
        resolved_output = Path(output_path).expanduser().resolve()
        inspection = ResumeInspection(
            output_path=str(resolved_output),
            final_exists=resolved_output.exists(),
            sidecar_exists=False,
            signature_match=False,
            completed_chunks=0,
            completed_output_frames=0,
            next_source_frame=0,
            total_output_frames=preflight.stage_plan.total_encoded_frames,
        )

    ndjson.emit(
        BackendEnvelopeType.RESUME_INSPECTION,
        ResumeInspectionResult(
            type=ResumeInspectionEventType.RESUME_INSPECTION,
            pipeline_kind=(ResumePipelineKind.STREAMING if processing_steps else ResumePipelineKind.FORMAT_CONVERSION),
            input_path=input_path,
            output_path=inspection.output_path,
            final_exists=inspection.final_exists,
            sidecar_exists=inspection.sidecar_exists,
            signature_match=inspection.signature_match,
            completed_chunks=inspection.completed_chunks,
            completed_output_frames=inspection.completed_output_frames,
            next_source_frame=inspection.next_source_frame,
            total_output_frames=inspection.total_output_frames,
        ),
    )
