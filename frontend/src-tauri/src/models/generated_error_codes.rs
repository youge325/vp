// Generated from contracts/backend-error-codes.schema.json. Do not edit.

use super::boundary::{BackendTaskErrorCode, TaskErrorCode};

pub(super) const fn backend_error_code_to_task_error_code(
    code: BackendTaskErrorCode,
) -> TaskErrorCode {
    match code {
        BackendTaskErrorCode::MissingFfmpeg => TaskErrorCode::MissingFfmpeg,
        BackendTaskErrorCode::MissingModel => TaskErrorCode::MissingModel,
        BackendTaskErrorCode::MissingTensorBackend => TaskErrorCode::MissingTensorBackend,
        BackendTaskErrorCode::MissingPythonDependency => TaskErrorCode::MissingPythonDependency,
        BackendTaskErrorCode::Cancelled => TaskErrorCode::Cancelled,
        BackendTaskErrorCode::ProcessFailed => TaskErrorCode::ProcessFailed,
        BackendTaskErrorCode::InvalidInput => TaskErrorCode::InvalidInput,
        BackendTaskErrorCode::InvalidConfig => TaskErrorCode::InvalidConfig,
        BackendTaskErrorCode::ResumeConflict => TaskErrorCode::ResumeConflict,
        BackendTaskErrorCode::IoError => TaskErrorCode::IoError,
        BackendTaskErrorCode::PersistenceFailed => TaskErrorCode::PersistenceFailed,
    }
}
