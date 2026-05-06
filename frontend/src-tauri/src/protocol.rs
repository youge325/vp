use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "kebab-case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum TaskEventName {
    TaskProgress,
    TaskCompleted,
    TaskError,
    TaskCancelled,
    TaskLog,
    TaskResumeStatus,
}

impl TaskEventName {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TaskProgress => "task-progress",
            Self::TaskCompleted => "task-completed",
            Self::TaskError => "task-error",
            Self::TaskCancelled => "task-cancelled",
            Self::TaskLog => "task-log",
            Self::TaskResumeStatus => "task-resume-status",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema, TS)]
#[serde(rename_all = "snake_case")]
#[ts(export, export_to = "../../src/types/generated/")]
pub enum TaskErrorCode {
    MissingFfmpeg,
    MissingModel,
    MissingTensorBackend,
    Cancelled,
    ProcessFailed,
    InvalidInput,
    InvalidConfig,
    ResumeConflict,
}

impl TaskErrorCode {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::MissingFfmpeg => "missing_ffmpeg",
            Self::MissingModel => "missing_model",
            Self::MissingTensorBackend => "missing_tensor_backend",
            Self::Cancelled => "cancelled",
            Self::ProcessFailed => "process_failed",
            Self::InvalidInput => "invalid_input",
            Self::InvalidConfig => "invalid_config",
            Self::ResumeConflict => "resume_conflict",
        }
    }
}

pub const TERMINAL_PROGRESS_PREFIX: &str = "[VP_PROGRESS]";
