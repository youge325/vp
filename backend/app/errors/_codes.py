"""Single source of truth for task error codes.

The codes here MUST match the Rust ``TaskErrorCode`` enum at
``frontend/src-tauri/src/models/task.rs`` (snake_case string values).
A schema-drift test asserts this equality via the ts-rs generated
JSON schema.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class TaskErrorCode(str, Enum):
    """Error codes synchronized with Rust ``protocol::TaskErrorCode``."""

    MISSING_FFMPEG = "missing_ffmpeg"
    MISSING_MODEL = "missing_model"
    MISSING_TENSOR_BACKEND = "missing_tensor_backend"
    MISSING_PYTHON_DEPENDENCY = "missing_python_dependency"
    CANCELLED = "cancelled"
    PROCESS_FAILED = "process_failed"
    SPAWN_FAILED = "spawn_failed"
    RUNTIME_PANIC = "runtime_panic"
    INVALID_INPUT = "invalid_input"
    INVALID_CONFIG = "invalid_config"
    RESUME_CONFLICT = "resume_conflict"
    IO_ERROR = "io_error"
    SCHEMA_MISMATCH = "schema_mismatch"
    PERSISTENCE_FAILED = "persistence_failed"
    # Phase 2.1 — 对应 Rust 层 BackendExit 拆分的新错误码。
    BACKEND_NO_JSON = "backend_no_json"
    BACKEND_ENVELOPE = "backend_envelope"
    CONTROLLER_UNAVAILABLE = "controller_unavailable"
    BACKEND_PROBE_FAILED = "backend_probe_failed"


ALL_CODES = frozenset(code.value for code in TaskErrorCode)


def error_code_to_wire(code: Any) -> str:
    """Return a Rust-schema-safe snake_case task error code.

    Internal Python code sometimes carries ``TaskErrorCode`` enum values and
    older worker paths accidentally serialized ``str(enum)`` values such as
    ``"TaskErrorCode.MISSING_MODEL"``. The NDJSON wire protocol must always
    use the enum value string, and unknown values degrade to ``process_failed``
    rather than producing an IPC schema mismatch in the Tauri host.
    """
    if isinstance(code, TaskErrorCode):
        return code.value

    if isinstance(code, str):
        stripped = code.strip()
        if stripped in ALL_CODES:
            return stripped
        prefix = f"{TaskErrorCode.__name__}."
        if stripped.startswith(prefix):
            enum_name = stripped[len(prefix) :]
            try:
                return TaskErrorCode[enum_name].value
            except KeyError:
                return TaskErrorCode.PROCESS_FAILED.value

    return TaskErrorCode.PROCESS_FAILED.value
