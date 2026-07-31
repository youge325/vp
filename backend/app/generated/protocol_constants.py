"""Generated from contracts/ipc-manifest.json. Do not edit."""

from enum import StrEnum

from app.generated import contracts as _contracts
from app.generated.bootstrap_constants import (
    ERROR_SUMMARY_LIMIT_BYTES as ERROR_SUMMARY_LIMIT_BYTES,
    NDJSON_LINE_LIMIT_BYTES as NDJSON_LINE_LIMIT_BYTES,
)


class BackendEnvelopeType(StrEnum):
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"
    RESUME_STATUS = "resume_status"
    INFO = "info"
    CHECK = "check"
    RESUME_INSPECTION = "resume_inspection"


TERMINAL_PROGRESS_PREFIX = "[VP_PROGRESS]"
STAGE_WORKER_EVENT_PREFIX = "VP_STAGE_EVENT "
STAGE_WORKER_COMMAND = ("-m", "app")
STAGE_WORKER_SUBCOMMAND = "stage-worker"
STAGE_WORKER_CONFIG_FLAG = "--config-json"
ONE_SHOT_STDOUT_LIMIT_BYTES = 8388608
STDERR_TAIL_LIMIT_BYTES = 65536
TERMINATION_REAP_TIMEOUT_MS = 5000
STAGE_WORKER_TERMINATION_REAP_TIMEOUT_MS = TERMINATION_REAP_TIMEOUT_MS

BACKEND_ENVELOPE_PAYLOAD_TYPES = {
    BackendEnvelopeType.PROGRESS: _contracts.TaskProgressPayload,
    BackendEnvelopeType.COMPLETED: _contracts.TaskCompletedPayload,
    BackendEnvelopeType.ERROR: _contracts.BackendTaskErrorPayload,
    BackendEnvelopeType.RESUME_STATUS: _contracts.ResumeStatusPayload,
    BackendEnvelopeType.INFO: _contracts.VideoInfo,
    BackendEnvelopeType.CHECK: _contracts.EnvironmentCheckResult,
    BackendEnvelopeType.RESUME_INSPECTION: _contracts.ResumeInspectionResult,
}

BACKEND_ENVELOPE_OPTIONAL_FIELDS = {
    BackendEnvelopeType.PROGRESS: frozenset(["metrics"]),
    BackendEnvelopeType.COMPLETED: frozenset([]),
    BackendEnvelopeType.ERROR: frozenset(["details"]),
    BackendEnvelopeType.RESUME_STATUS: frozenset([]),
    BackendEnvelopeType.INFO: frozenset([]),
    BackendEnvelopeType.CHECK: frozenset([]),
    BackendEnvelopeType.RESUME_INSPECTION: frozenset([]),
}

BACKEND_ENVELOPE_PRESERVES_DISCRIMINATOR = frozenset(
    {
        BackendEnvelopeType.RESUME_INSPECTION,
    }
)
