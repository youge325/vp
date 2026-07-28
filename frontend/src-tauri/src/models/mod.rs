//! Boundary models generated from the repository JSON Schema contracts.
//!
//! Keep domain-facing import paths narrow: configuration consumers use
//! `models::config`, task consumers use `models::task`, and shell-only
//! environment/cache types stay crate-private.

mod boundary {
    typify::import_types!(schema = "../../contracts/boundary.schema.json");
}

pub mod config {
    pub use super::boundary::{
        DecodeConfig, DecodeMode, EncodeConfig, FilterStep, FilterStepKind, FpsMode,
        InterpolationConfig, OutputConfig, PostprocessConfig, PreprocessConfig, ProcessOrder,
        RateControlConfig, RateControlMode, SuperResolutionConfig, TensorBackend, WorkbenchPreset,
        WorkflowConfig,
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
    EnvironmentCheckResult, EnvironmentCheckSource, ShellTaskErrorCode, TaskControlKind,
    TaskErrorCode, WorkbenchPresetEntry,
};
pub(crate) use config::WorkbenchPreset;
pub(crate) use task::{
    ResumeInspectionResult, ResumeStatusPayload, TaskCancelledPayload, TaskCancelledReason,
    TaskCompletedPayload, TaskErrorPayload, TaskLogPayload, TaskProgressPayload, TaskRequest,
    VideoInfo,
};

impl From<BackendTaskErrorPayload> for TaskErrorPayload {
    fn from(payload: BackendTaskErrorPayload) -> Self {
        let code = serde_json::from_value(
            serde_json::to_value(payload.code)
                .expect("generated backend error codes must serialize"),
        )
        .expect("backend error-code schema must remain a subset of the full error-code schema");
        Self {
            code,
            message: payload.message,
            details: payload.details,
        }
    }
}

#[cfg(test)]
mod tests;
