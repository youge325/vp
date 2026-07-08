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
from app.planning.processing_steps import (
    AlgorithmType,
    ProcessingStep,
    ProcessingStepInput,
    normalize_processing_step,
    normalize_processing_steps,
    processing_steps_to_jsonable,
)
from app.planning.stage_plan import (
    StagePlan,
    build_signature,
    build_stage_plan,
    estimate_encoded_output_frames,
    resolve_video_info,
)
from app.planning.workflow_steps import (
    PROCESS_LABEL_MAP,
    PROCESS_ORDER_MAP,
    processing_needs_interpolation,
    resolve_expected_output_frames,
    resolve_primary_algorithm,
    resolve_processing_steps,
    resolve_workflow_and_output_fps,
)
from app.planning.workflow_validation import (
    get_onnx_model_name,
    validate_onnx_models_for_workflow,
    verify_model_availability,
    verify_super_resolution_backend,
)

__all__ = [
    "ResumeDecision",
    "ResumeKind",
    "ResumeMode",
    "ResumeState",
    "SegmentManifest",
    "SegmentRecord",
    "AlgorithmType",
    "ProcessingStep",
    "ProcessingStepInput",
    "normalize_processing_step",
    "normalize_processing_steps",
    "processing_steps_to_jsonable",
    "StagePlan",
    "build_signature",
    "build_stage_plan",
    "estimate_encoded_output_frames",
    "resolve_video_info",
    "PROCESS_LABEL_MAP",
    "PROCESS_ORDER_MAP",
    "processing_needs_interpolation",
    "resolve_expected_output_frames",
    "resolve_primary_algorithm",
    "resolve_processing_steps",
    "resolve_workflow_and_output_fps",
    "get_onnx_model_name",
    "validate_onnx_models_for_workflow",
    "verify_model_availability",
    "verify_super_resolution_backend",
]
