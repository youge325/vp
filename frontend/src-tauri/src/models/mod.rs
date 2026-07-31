//! Boundary models generated from the repository JSON Schema contracts.
//!
//! Keep domain-facing import paths narrow: configuration consumers use
//! `models::config`, task consumers use `models::task`, and shell-only
//! environment/cache types stay crate-private.

mod boundary {
    typify::import_types!(schema = "../../contracts/boundary.schema.json");
}
mod generated_error_codes;

pub mod config {
    pub use super::boundary::{
        DecodeConfig, DecodeMode, EncodeConfig, FilterStep, FilterStepKind, FpsMode,
        InferenceEngine, InterpolationConfig, OutputConfig, PostprocessConfig, PreprocessConfig,
        ProcessOrder, RateControlConfig, RateControlMode, SuperResolutionConfig, TensorBackend,
        WorkbenchPreset, WorkflowConfig,
    };
}

pub mod task {
    pub use super::boundary::{
        ResumeInspectionEventType, ResumeInspectionResult, ResumeMode, ResumePipelineKind,
        ResumeStatusPayload, TaskCancelledPayload, TaskCancelledReason, TaskCompletedPayload,
        TaskErrorPayload, TaskLogPayload, TaskProgressPayload, TaskRequest, VideoInfo,
    };
}

pub(crate) use boundary::{
    BackendTaskErrorCode, BackendTaskErrorPayload, EnvironmentCacheEntry, EnvironmentCheckPayload,
    EnvironmentCheckResult, EnvironmentCheckSource, RuntimeConfigBundle, ShellTaskErrorCode,
    TaskControlKind, TaskErrorCode, WorkbenchPresetEntry,
};
pub(crate) use config::WorkbenchPreset;
pub(crate) use task::{
    ResumeInspectionResult, ResumeStatusPayload, TaskCancelledPayload, TaskCancelledReason,
    TaskCompletedPayload, TaskErrorPayload, TaskLogPayload, TaskProgressPayload, TaskRequest,
    VideoInfo,
};

impl From<BackendTaskErrorPayload> for TaskErrorPayload {
    fn from(payload: BackendTaskErrorPayload) -> Self {
        Self {
            code: generated_error_codes::backend_error_code_to_task_error_code(payload.code),
            message: payload.message,
            details: payload.details,
        }
    }
}

#[cfg(test)]
mod tests;
