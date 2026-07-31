"""Generated import-safe bootstrap constants. Do not edit."""

NDJSON_LINE_LIMIT_BYTES = 1048576
ERROR_SUMMARY_LIMIT_BYTES = 8192

BACKEND_TASK_ERROR_CODES = frozenset(
    {
        "missing_ffmpeg",
        "missing_model",
        "missing_tensor_backend",
        "missing_python_dependency",
        "cancelled",
        "process_failed",
        "invalid_input",
        "invalid_config",
        "resume_conflict",
        "io_error",
        "persistence_failed",
    }
)
